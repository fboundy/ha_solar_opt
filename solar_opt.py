# %%
import appdaemon.plugins.hass.hassapi as hass
import mqttapi as mqtt
import pandas as pd
from math import ceil

# %%
# from json import dumps

VERSION = "1.1.1"

DEBUG = True
DEBUG_TIME_NOW = pd.Timestamp("2023-03-03 06:00:00+00:00")
FAKE_AGILE_IMPORT = False
FAKE_AGILE_DIFF = 50

OUTPUT_SOC_ENTITY = "sensor.solaropt_optimised_target_soc"
OUTPUT_START_ENTITY = "sensor.solaropt_charge_start"
OUTPUT_END_ENTITY = "sensor.solaropt_charge_end"
OUTPUT_CURRENT_ENTITY = "sensor.solaropt_charge_current"

TARIFFS = ["import", "export"]
SOLCAST_ENTITY_TODAY = "sensor.solcast_forecast_today"
SOLCAST_ENTITY_TOMORROW = "sensor.solcast_forecast_tomorrow"


class SolarOpt(hass.Hass):
    def hass2df(self, entity_id, days=2, log=False):
        hist = self.get_history(entity_id=entity_id, days=days)
        if log:
            self.log(hist)
        df = pd.DataFrame(hist[0]).set_index("last_updated")["state"]
        df.index = pd.to_datetime(df.index)
        df = df[df != "unavailable"]
        df = df[df != "unknown"]
        return df

    def initialize(self):
        self.log(f"*************** SolarOpt v{VERSION} ***************")
        self.adapi = self.get_ad_api()
        self.mqtt = self.get_plugin_api("MQTT")
        self.set_default_params()
        self.load_args()
        self.load_tariffs()
        # Optimise on an EVENT trigger:
        self.listen_event(self.optimise_event, "SOLAR_OPT")
        # Optimise when the Solcast forecast changes:
        self.listen_state(self.optimise_state_change, SOLCAST_ENTITY_TODAY)
        self.log(f"************ SolarOpt Initialised ************")
        self.optimise()
        self.log(f"******** Waiting for SOLAR_OPT Event *********")

    def set_default_params(self):
        self.params = {}

    def load_args(self, keys=None):
        self.pointers = []
        if keys is None:
            keys = self.args.keys()
        if DEBUG:
            self.log(self.args)
        for key in keys:
            # Attempt to read entity states for all string paramters unless they start with"entity_id":
            if isinstance(self.args[key], str) and self.entity_exists(self.args[key]) and (key[:9] != "entity_id"):
                self.params[key] = self.get_state(self.args[key])
                # If these entities are inputs and they change then we need to trigger automatically
                if "input" in self.args[key]:
                    self.listen_state(self.optimise_state_change, self.args[key])

            else:
                if isinstance(self.args[key], str):
                    for x in ["sensor", "input"]:
                        if x in self.args[key] and not self.entity_exists(self.args[key]):
                            self.log(f"WARNING: {self.args[key]} does not resolve to a valid entity")

                self.params[key] = self.args[key]

            # Try to coerce it to an int
            try:
                self.params[key] = int(self.params[key])
            except Exception as e:
                # Then a float
                try:
                    self.params[key] = float(self.params[key])
                except Exception as e:
                    # Can't coerce from on/off to boolean so manually do this
                    if self.params[key] in ["on", "off"]:
                        self.params[key] = self.params[key] == "on"

            if DEBUG:
                self.log(f"Loaded parameter {key}: {self.params[key]} as a {type(self.params[key])}")

    def mpan_sensor(self, tariff):
        mpan = self.params[f"octopus_{tariff}_mpan"]
        sensor = f"sensor.octopus_energy_electricity_{self.params['octopus_serial'].lower()}_{mpan}"
        if tariff == "export":
            sensor += "_export_current_rate"
        else:
            sensor += "_current_rate"
        return sensor

    def load_tariffs(self):
        # Load the data from the sensors created by the Octopus Energy integration:
        # https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy

        self.sensors = {}

        if not self.params["manual_tariff"]:
            # If the auto option is selected, try to get all the information automatically:
            if self.params["octopus_auto"]:
                if DEBUG:
                    self.log(f"Trying to auto detect Octopus tariffs")
                current_rate_sensors = [
                    name
                    for name in self.get_state("sensor").keys()
                    if ("octopus_energy_electricity" in name and "current_rate" in name)
                ]
                sensors = {}
                sensors["import"] = [x for x in current_rate_sensors if not "export" in x]
                sensors["export"] = [x for x in current_rate_sensors if "export" in x]
                for tariff in TARIFFS:
                    if sensors[tariff]:
                        self.sensors[tariff] = sensors[tariff][0]
                        self.params["octopus_serial"] = self.sensors[tariff].split("_")[3]
                        self.params[f"octopus_{tariff}_mpan"] = self.sensors[tariff].split("_")[4]
                        tariff_code = self.get_state(self.sensors[tariff], attribute="all")["attributes"]["rate"][
                            "tariff_code"
                        ]
                        self.params[f"octopus_{tariff}_tariff_code"] = tariff_code
                        self.log(f"Got {tariff.title()} sensor automatically. Tariff code: {tariff_code}")

            else:
                if DEBUG:
                    self.log(f"Loading Octopus tariffs from specified MPANs")
                for tariff in TARIFFS:
                    self.sensors[tariff] = self.mpan_sensor(tariff)
        else:
            if DEBUG:
                self.log(f"Manual tariff specified. Not loading tariffs from Octopus integration.")

    def optimise_state_change(self, entity, attribute, old, new, kwargs):
        self.log(f"*********  State change triggered **********")
        self.log(f"Entity: {entity}")
        self.log(f"From: {old}")
        self.log(f"To: {new}")

        # Update the params
        self.load_args([k for k, v in self.args.items() if v == entity])
        self.optimise()

    def optimise_event(self, event_name, data, kwargs):
        self.log(f"********* {event_name} Event triggered **********")
        self.optimise()

    def optimise(self):
        # initialse a DataFrame to cover today and tomorrow at 30 minute frequency
        self.df = pd.DataFrame(
            index=pd.date_range(
                pd.Timestamp.now().tz_localize("UTC").normalize(),
                pd.Timestamp.now().tz_localize("UTC").normalize() + pd.Timedelta(days=2),
                freq="30T",
                inclusive="left",
            ),
            data={"import": 0, "export": 0},
        )

        self.df["period_start"] = self.df.index.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        self.freq = self.df.index.freq / pd.Timedelta("60T")

        # Load prices
        try:
            if not self.load_prices():
                raise Exception

        except Exception as e:
            self.log(f"Unable to load price data: {e}")
            return False

        # Load Solcast
        try:
            if not self.load_solcast():
                raise Exception

        except Exception as e:
            self.log(f"Unable to load solar forecast: {e}")
            return False

        # Load the expected consumption
        try:
            if not self.load_consumption():
                raise Exception

        except Exception as e:
            self.log(f"Unable to load estimated consumption: {e}")
            return False

        # Calculate when the next charging slot is
        self.calc_charging_slot()

        # Calculate the flows and cashflow with no charging
        self.calc_flows()
        self.log(f"Reference cost (no solar):  GBP{self.df['ref_cost'].sum():5.2f}")
        self.log(f"Net cost (no optimisation): GBP{self.df['net_cost'].sum():5.2f}")

        if self.params["optimise_flag"]:
            self.log("Optimising target SOC")
            soc_range = list(range(int(ceil(self.params["maximum_dod_percent"] / 5) * 5), 101, 5))
        else:
            soc_range = [int(float(self.params["default_target_soc"]))]
            self.log(f"Using default target SOC of {soc_range[0]}%")

        nc = []
        for target_soc in soc_range:
            self.calc_flows(target_soc)
            nc.append(self.df["net_cost"].sum())

        nc_opt = min(nc)
        self.optimised_target_soc = soc_range[nc.index(nc_opt)]
        self.calc_flows(self.optimised_target_soc)

        nc_opt = self.df["net_cost"].sum()
        self.log((f"Optimum SOC: {self.optimised_target_soc}% with net cost GBP{nc_opt:5.2f}"))

        self.write_output()

    def write_to_hass(self, entity, state, attributes):
        try:
            self.my_entity = self.get_entity(entity)
            self.my_entity.set_state(state=state, attributes=attributes)

        except Exception as e:
            self.log(f"Couldn't write to entity {entity}: {e}")

    def write_output(self):
        self.write_to_hass(
            entity=OUTPUT_SOC_ENTITY,
            state=self.optimised_target_soc,
            attributes={
                "unit_of_measurement": "%",
                "state_class": "measurement",
                "device_class": "battery",
                "friendly name": "Solar_Opt Optimised Target SOC",
                "optimised_soc": self.df[["period_start", "soc"]].to_dict("records"),
                "raw_soc": self.df[["period_start", "soc0"]]
                .set_axis(["period_start", "soc"], axis=1)
                .to_dict("records"),
                "consumption": (self.df[["period_start", "consumption"]]).to_dict("records"),
            },
        )

        self.write_to_hass(
            entity=OUTPUT_START_ENTITY,
            state=self.charge_start_datetime,
            attributes={
                "friendly name": "Solar_Opt Next Charge Period Start",
            },
        )

        self.write_to_hass(
            entity=OUTPUT_END_ENTITY,
            state=self.charge_end_datetime,
            attributes={
                "friendly name": "Solar_Opt Next Charge Period End",
            },
        )

        self.write_to_hass(
            entity=OUTPUT_CURRENT_ENTITY,
            state=round(self.charge_current, 2),
            attributes={
                "friendly name": "Solar_Opt Charging Current",
                "unit_of_measurement": "A",
                "state_class": "measurement",
                "device_class": "current",
            },
        )

    def calc_charging_slot(self):
        time_now = pd.Timestamp.now().tz_localize("UTC")
        if DEBUG:
            time_now = DEBUG_TIME_NOW

        if bool(self.params["charge_auto_select"]):
            if not "AGILE" in self.params["octopus_import_tariff_code"]:
                # Fixed time slot calculation
                night_rate = self.df["import"].min()

                # look forward from now and see when the next slot at this rate starts:
                self.charge_start_datetime = self.df[
                    (self.df["import"] == night_rate) & (self.df.index >= time_now - pd.Timedelta("30T"))
                ].index[0]
                # if we are in the slot then set the slot start to now:
                self.charge_start_datetime = max([time_now, self.charge_start_datetime])
                self.charge_end_datetime = self.df[
                    (self.df["import"] != night_rate) & (self.df.index >= self.charge_start_datetime)
                ].index[0]

            else:
                # TO-DO:
                # Still need to work out how to deal with Agile the best time starts now....

                # For AGILE we are calulating the maximum slot length
                # We first calulate the maximum energy required:
                self.log(self.params["maximum_dod_percent"])
                max_energy = (
                    (self.params["default_target_soc"] - self.params["maximum_dod_percent"])
                    / 100
                    * self.params["battery_capacity_Wh"]
                )

                # Hours required depends on power and effiency of charger
                max_charge_hours = (
                    max_energy / self.params["charger_power_watts"] / self.params["charger_efficiency_percent"] * 100
                )

                # Round up to nearest half hour and count slots required
                slots_required = int((max_charge_hours - 0.01) / self.freq)
                self.log(f"For Agile charging {slots_required} half-hour slots are required")

                # Now we take the rolling average of the price over the required slots
                df = (
                    self.df["import"][
                        (self.df.index >= time_now)
                        & (self.df.index < time_now + pd.Timedelta(hours=23 + slots_required * 2))
                    ]
                    .rolling(slots_required)
                    .mean()
                    .dropna()
                )
                self.log(df)
                min_price = df.min()

                self.charge_start_datetime = df[df == min_price].index[0]

                # Check to see if the price now < average charge price in which case recalculate from current SOC to target
                if float(self.get_state(self.sensors["import"])) * 100 < min_price:
                    energy = (
                        (
                            self.params["default_target_soc"]
                            - float(self.get_state(self.params["entity_id_battery_soc"]))
                        )
                        / 100
                        * self.params["battery_capacity_Wh"]
                    )

                    # Calculate what the remaining energy at the end of this periof would be if we started charging now
                    fraction_remaining = (time_now.round("30T") - time_now) / pd.Timedelta("60T")

                    energy -= (
                        fraction_remaining
                        * self.params["charger_power_watts"]
                        * self.params["charger_efficiency_percent"]
                        / 100
                    )

                    charge_hours = (
                        energy / self.params["charger_power_watts"] / self.params["charger_efficiency_percent"] * 100
                    )
                    slots_required = int((charge_hours - 0.01) / self.freq)
                    self.charge_start_datetime = time_now

                self.charge_end_datetime = self.charge_start_datetime + pd.Timedelta(minutes=slots_required * 30)

        self.report_datetime = self.charge_end_datetime.normalize() + pd.Timedelta("1D")
        self.df = self.df[self.df.index < self.report_datetime]
        self.chg_mask = (self.df.index >= self.charge_start_datetime) & (self.df.index < self.charge_end_datetime)
        self.log(f"Charging slot start {self.charge_start_datetime}")
        self.log(f"Charging slot end {self.charge_end_datetime}")

    def calc_flows(self, target_soc=None):
        self.initial_chg = (
            float(self.get_state(self.params["entity_id_battery_soc"])) / 100 * self.params["battery_capacity_Wh"]
        )
        solar_source = self.params["solar_forecast"]
        if solar_source == "Solcast Swanson":
            weights = {"Solcast_p10": 0.3, "Solcast": 0.4, "Solcast_p90": 0.3}
        else:
            weights = {solar_source: 1}

        self.df["net_cost"] = 0
        self.df["soc"] = 0
        self.df["ref_cost"] = -self.df["consumption"] * self.df["import"] / 100 / 1000 * self.freq

        for source in weights:
            battery_flows = self.df[source] + self.df["consumption"]
            if target_soc is not None:
                hours = (self.charge_end_datetime - self.charge_start_datetime).seconds / 3600
                target_chg = target_soc * self.params["battery_capacity_Wh"] / 100
                chg_start = self.df["chg0"].loc[self.charge_start_datetime]
                if target_chg > chg_start:
                    charge_flow = (target_chg - chg_start) / hours / self.params["charger_efficiency_percent"] * 100
                    battery_flows[self.chg_mask] = charge_flow
                    self.charge_current = charge_flow / self.params["battery_voltage"]

            chg = [self.initial_chg]
            for flow in battery_flows:
                if flow < 0:
                    flow = flow / self.params["inverter_efficiency_percent"] * 100
                else:
                    flow = flow * self.params["charger_efficiency_percent"] / 100
                chg.append(
                    round(
                        max(
                            [
                                min([chg[-1] + flow * self.freq, self.params["battery_capacity_Wh"]]),
                                self.params["maximum_dod_percent"] * self.params["battery_capacity_Wh"] / 100,
                            ]
                        ),
                        1,
                    )
                )

            self.df["chg"] = chg[1:]
            self.df["battery_flow"] = (-pd.Series(chg).diff() / self.freq)[1:].to_list()

            self.df.loc[self.df["battery_flow"] > 0, "battery_flow"] = (
                self.df["battery_flow"] * self.params["inverter_efficiency_percent"] / 100
            )
            self.df.loc[self.df["battery_flow"] < 0, "battery_flow"] = (
                self.df["battery_flow"] / self.params["charger_efficiency_percent"] * 100
            )
            self.df["grid_flow"] = -(self.df[source] + self.df["consumption"] + self.df["battery_flow"]).round(2)

            self.df["net_cost"] += (
                (self.df["import"] * self.df["grid_flow"]).clip(0) / 100 / 1000 * self.freq * weights[source]
            )
            self.df["net_cost"] += (
                (self.df["export"] * self.df["grid_flow"]).clip(upper=0) / 100 / 1000 * self.freq * weights[source]
            )

            self.df["soc"] += (self.df["chg"] / self.params["battery_capacity_Wh"] * 100).astype(int) * weights[source]

        if target_soc is None:
            self.df["chg0"] = self.df["chg"]
            self.df["soc0"] = self.df["soc"]

    def load_prices(self):
        try:
            if self.params["manual_tariff"]:
                if DEBUG:
                    self.log("Loading manual tariffs")

                for tariff in TARIFFS:
                    valid_prices = {}
                    # Get all the import prices
                    prices = [x for x in self.params.keys() if f"{tariff}_tariff" in x and "price" in x]
                    if DEBUG:
                        self.log(f"{tariff.title()}: {prices}")

                    # If there is only one price then set it for the entire period
                    if len(prices) == 1:
                        self.df[tariff] = self.params[prices[0]]

                    else:
                        for price in prices:
                            start_time = price.replace("price", "start")
                            # Check there is a starttime for the price
                            if price in self.params.keys():
                                # Add an entry for yestersday, today and tomorrow at the price
                                for days in range(-1, 2):
                                    valid_prices[
                                        pd.Timestamp(self.params[start_time]).tz_localize("UTC")
                                        + pd.Timedelta(days=days)
                                    ] = self.params[price]
                        # Sort the dict
                        valid_prices = dict(sorted(valid_prices.items()))
                        if DEBUG:
                            self.log(f"Valid Imports: {valid_prices}")

                        for start_datetime in valid_prices:
                            self.df.loc[self.df.index >= start_datetime, tariff] = valid_prices[start_datetime]

                    if DEBUG:
                        self.log(self.df[tariff])

            else:
                if DEBUG:
                    self.log("Loading sensor-based tariffs")

                for tariff in TARIFFS:
                    sensor = self.sensors[tariff]
                    self.log(f"{tariff.title()} sensor: {sensor}")

                    try:
                        # Read the price from the Octopus sensor attribute and convert to a DataFrame
                        prices = self.get_state(sensor, attribute="all")["attributes"]["rates"]

                    except Exception as e:
                        self.log(f"Attributes unavailable for sensor: {sensor}")
                        self.log(f"No {tariff} price data available: {e}")

                    df = pd.DataFrame(prices)
                    df = df.set_index("from")["rate"]

                    # Convert the index to datetime
                    df.index = pd.to_datetime(df.index)

                    # If it's only today's data pad it out assuming tomorrow = today
                    if len(df) < 94:
                        dfx = df.copy()
                        dfx.index = dfx.index + pd.Timedelta("1D")
                        df = pd.concat([df, dfx])

                    # Fill andy missing data (after 23:00) with the 22:30 data
                    self.df[tariff] = df
                    self.df[tariff].fillna(self.df[tariff].dropna()[-1], inplace=True)

                    self.log(f"** {tariff.title()} tariff price data loaded OK **")

                # DEBUG
                if FAKE_AGILE_IMPORT:
                    self.df["import"] = self.df["export"] + FAKE_AGILE_DIFF
                    self.params["octopus_import_tariff_code"] = "FAKE_AGILE"

            return True

        except Exception as e:
            if DEBUG:
                self.log(f"Error loading price data: {e}")
            return False

    def load_solcast(self):
        self.log("Getting Solcast data")
        try:
            solar = self.get_state(SOLCAST_ENTITY_TODAY, attribute="all")["attributes"]["detailedForecast"]
            solar += self.get_state(SOLCAST_ENTITY_TOMORROW, attribute="all")["attributes"]["detailedForecast"]

        except Exception as e:
            self.log(f"Failed to get solcast attributes: {e}")
            return False

        try:
            # Convert to timestamps
            for s in solar:
                s["period_start"] = pd.Timestamp(s["period_start"])

            df = pd.DataFrame(solar)
            df = df.set_index("period_start")
            df.index = pd.to_datetime(df.index)
            df = df.set_axis(["Solcast", "Solcast_p10", "Solcast_p90"], axis=1)

            # Convert from kWh/30min period to W
            df *= 1000 / self.freq

            self.df = pd.concat([self.df, df.fillna(0)], axis=1)
            self.log("** Solcast forecast loaded OK **")
            return True

        except Exception as e:
            self.log(f"Error loading Solcast: {e}")
            return False

    def load_consumption(self):
        self.log("Getting expected consumption data")

        try:
            # load history fot the last N days from the specified sensor
            df = self.hass2df(self.params["entity_id_consumption"], days=int(self.params["consumption_history_days"]))

        except Exception as e:
            self.log(f"Unable to get historical consumption from {self.params['entity_id_consumption']}")
            self.log(f"Error: {e}")
            return False

        try:
            # df = pd.DataFrame(hist[0]).set_index("last_updated")["state"]
            df.index = pd.to_datetime(df.index)
            df = pd.to_numeric(df, errors="coerce").dropna().resample("30T").mean()

            # Group by time and take the mean
            df = df.groupby(df.index.time).aggregate(self.params["consumption_grouping"]) * -1
            df.name = "consumption"

            self.df["time"] = self.df.index.time
            self.df = self.df.merge(df, "left", left_on="time", right_index=True)

            self.df = self.df[self.df.index >= pd.Timestamp.now().tz_localize("UTC") - pd.Timedelta("30T")]
            self.log("** Estimated consumption loaded OK **")
            return True

        except Exception as e:
            self.log(f"Error loading consumption data: {e}")
            return False


# %%
