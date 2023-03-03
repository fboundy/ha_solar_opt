# Home Assitant Solar Optimiser

Solar / Battery Charging Optimisation for Home Assistant

<h2>Pre-requisites</h2>

<h3>Solcast Hobby Account</h>

<b>Solar_Opt</b> relies on solar forecasts data from Solcast. You can sign up for a Private User account [here](https://solcast.com/free-rooftop-solar-forecasting?gclid=CjwKCAiAr4GgBhBFEiwAgwORrQp6co5Qw8zNjEgUhBee7Hfa39_baEWG-rB-GB3FFpiaIA5eAPHhahoC3vAQAvD_BwE). This licence gives you 10 (it used to be 50 :-( ) API calls a day.

<h3>Solcast PV Solar Integration</h3>

This integrates Solcast into Home Assistant. Once installed configure using your Solcast API Key. Unless you have a legacy account with 50 API calls I suggest you tick the option to <b>Disable auto API polling</b> and set up an automation to update according to your desired schedule. Once every 3 hours will work. I update more frequently overnight while charging.

<h3>AppDaemon</h3>

The <b>Solar_Opt</b> python script currently runs under AppDaemon.

AppDaemon is a loosely coupled, multi-threaded, sandboxed python execution environment for writing automation apps for home automation projects, and any environment that requires a robust event driven architecture. The simplest way to install it on Home Assistantt is using the dedicated add-on:

1. Click the Home Assistant My button below to open the add-on on your Home Assistant instance:

   [![](https://camo.githubusercontent.com/c16bd5d7acfc6d5163636b546783e9217e27a401c1ac5bfd93a2ef5fa23e15fe/68747470733a2f2f6d792e686f6d652d617373697374616e742e696f2f6261646765732f73757065727669736f725f6164646f6e2e737667)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=a0d7b954_appdaemon&repository_url=https%3A%2F%2Fgithub.com%2Fhassio-addons%2Frepository)

2. Click on <b>Install</b>

3. Turn on <b>Watchdog</b> and <b>Auto update</b>

4. Click on <b>Configuration</b> at the top

5. Click the 3 dots and <b>Edit in YAML</b>:

   ```
   init_commands: []
   python_packages:
     - pandas
   system_packages: []

   ```

6. Go back to the <b<Info</b> page and click on <b>Start</b>

7. Click on <b>Log</b>. Appdaemon will download and install numpy and pandas. Click on <b>Refresh</b> until you see:

   ```
   INFO AppDaemon: Initializing app hello_world using class HelloWorld from module hello
   INFO hello_world: Hello from AppDaemon
   INFO hello_world: You are now ready to run Apps!
   INFO AppDaemon: App initialization complete
   INFO AppDaemon: New client Admin Client connected
   ```

That's it. AppDaemon is up and running. There is futher documentation for the on the [Add-on](https://github.com/hassio-addons/addon-appdaemon/blob/main/appdaemon/DOCS.md) and for [AppDaemon](https://appdaemon.readthedocs.io/en/latest/)

<h3>Home Assistant Octopus Energy Integration (Optional)</h3>

This integration will pull Octopus Price data in to Home Assistant [Github](https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy). If you have an Economy 7 or other fixed time of use import this can also be set up manually.

<h2>Installation</h2>

<h2>Configuration</h2>

All configuration is done by editing the parameters in the `/config/appdaemon/apps/ha_solar_opt/config.yaml` file. Many of the parameters can also be pointed to a Home Assistant entity rather than entering the parameter explicitly. This allows parameters to be updated dynamically from Home Assistant. In the example below `maximum_dod_percent` is taken from a sensor but `charger_power_watts` is set explicitly:

    maximum_dod_percent: sensor.solis_overdischarge_soc
    charger_power_watts: 3000

<h3>Required parameters:</h3>

| Name          |  Type   |   Default   | Can Point to Entity | Description                                                            |
| ------------- | :-----: | :---------: | :-----------------: | ---------------------------------------------------------------------- |
| module        | string  | `solar_opt` |       `false`       | Internal reference for AppDaemon <b>DO NOT EDIT</b>                    |
| class         | string  | `SolarOpt`  |       `false`       | Internal reference for AppDaemon <b>DO NOT EDIT</b>                    |
| manual_tariff | boolean |   `false`   |       `false`       | Use manual tariff data rather than from the Octopus Energy integration |

<h3>Manual Tariff Parameters</h3>

These are all required if `manual_tariff` is `true`. Any number of import or export time periods can be specified using sequential suffixes `_1`, `_2` etc. Each time period must have a start time and a price. Any periods with one and not the other will be ignored.

| Name                  |  Type   | Default | Can Point to Entity | Description                                |
| --------------------- | :-----: | :-----: | :-----------------: | ------------------------------------------ |
| import_tariff_1_price | `float` |         |       `true`        | Import prices p/kWh for Import Time Slot 1 |
| import_tariff_1_start | `time`  |         |       `true`        | Start time (UTC) for Import Time Slot 1    |
| import_tariff_2_price | `float` |         |       `true`        | Import prices p/kWh for Import Time Slot 2 |
| import_tariff_2_start | `time`  |         |       `true`        | Start time (UTC) for Import Time Slot 2    |
| export_tariff_1_price | `float` |         |       `true`        | Export prices p/kWh for Export Time Slot 1 |
| export_tariff_1_start | `time`  |         |       `true`        | Start time (UTC) for Export Time Slot 1    |

<h3>Octopus Account Parameters</h3>

These are required if `manual_tariff` is `false`. If `octopus_auto` is `true` the remaining parameters will be detected automatically and can be omitted. Optionally (and be default) these parameters can also be read from the `secrets.yaml` file.

| Name                       |  Type   |           Default           | Can Point to Entity | Description                                                                                                                                                                                       |
| -------------------------- | :-----: | :-------------------------: | :-----------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| octopus_auto               | boolean |           `true`            |       `false`       | Automatically get as many as possible of the remaining Octopus parameters directly from the Octopus Energy integration. Any that are missing will be taken from the explictly defined parameters. |
| octopus_import_mpan        | string  | !secret octopus_import_mpan |       `false`       | The MPAN of the Octopus import meter                                                                                                                                                              |
| octopus_export_mpan        | string  | !secret octopus_export_mpan |       `false`       | The MPAN of the Octopus export meter. Omit if there is no export                                                                                                                                  |
| octopus_serial             | string  |   !secret octopus_serial    |       `false`       | The Octopus meter serial number                                                                                                                                                                   |
| octopus_import_tariff_code | string  |                             |       `false`       | The Octopus import tariff code                                                                                                                                                                    |
| octopus_export_tariff_code | string  |                             |       `false`       | The Octopus export tariff code. Omit if there is no export                                                                                                                                        |

<h3>Charging Time Parameters</h3>

If `charge_auto_select` is `true` the remaining parameters will be detected automatically and can be omitted.

<h2>Triggering the App</h2>

The app will load into AppDaemon on startup. To check open the [AppDaemon UI Main Log](http://homeassistant.local:5050/aui/index.html#/logs). If it is blank simply open and save `solar_opt.py` file to force an update. You should see:

    2023-03-03 10:11:12.803829 INFO solar_opt: ******** Waiting for SOLAR_OPT Event *********
    2023-03-03 10:11:12.801661 INFO solar_opt: ************ SolarOpt Initialised ************
    2023-03-03 10:11:12.778445 INFO solar_opt: *************** SolarOpt v0.1.0 ***************
    2023-03-03 10:11:12.765458 INFO AppDaemon: Initializing app solar_opt using class SolarOpt from module solar_opt
    2023-03-03 10:11:12.736458 INFO AppDaemon: Reloading Module: /config/appdaemon/apps/ha_solar_opt/solar_opt.py

The app is triggered by firing the Home Assistant Event `SOLAR_OPT` which can be done from <b>Developer Tools</b> or via an Automation. If you manually fire an event you should see something like the below appear in the log:

    2023-03-03 10:19:00.841601 INFO solar_opt: Optimum SOC: 20% with net cost GBP 1.90
    2023-03-03 10:19:00.257332 INFO solar_opt: Net cost (no optimisation): GBP 1.94
    2023-03-03 10:19:00.254542 INFO solar_opt: Reference cost (no solar): GBP10.29
    2023-03-03 10:19:00.205972 INFO solar_opt: Charging slot end 2023-03-04 07:30:00+00:00
    2023-03-03 10:19:00.201941 INFO solar_opt: Charging slot start 2023-03-04 00:30:00+00:00
    2023-03-03 10:19:00.186961 INFO solar_opt: ** Estimated load loaded OK **
    2023-03-03 10:18:58.033455 INFO solar_opt: Getting expected load data
    2023-03-03 10:18:58.031026 INFO solar_opt: ** Solcast forecast loaded OK **
    2023-03-03 10:18:58.007462 INFO solar_opt: Getting Solcast data
    2023-03-03 10:18:58.005448 INFO solar_opt: ** Export tariff price data loaded OK **
    2023-03-03 10:18:57.986234 INFO solar_opt: Export sensor: sensor.octopus_energy_electricity_19m1234567_1650000123456_export_current_rate
    2023-03-03 10:18:57.983947 INFO solar_opt: ** Import tariff price data loaded OK **
    2023-03-03 10:18:57.960583 INFO solar_opt: Import sensor: sensor.octopus_energy_electricity_19m1234567_1650000654321_current_rate
    2023-03-03 10:18:57.945932 INFO solar_opt: ********* SOLAR_OPT Event triggered **********

<h2>Output</h2>

Solar Opt writes to the following Home Assistant enities:

| Name                                 | State / Attributes |       Type        | Description                    |
| ------------------------------------ | :----------------: | :---------------: | ------------------------------ |
| sensor.solaropt_optimised_target_soc |       state        |       `int`       | Optimised Target Charging SOC  |
|                                      |        soc         | `list` of `dict`s | Forecast Optimised SOC vs Time |

<h2>Using the App

<h2>Plotting Output and Input Data
