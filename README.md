# Home Assitant Solar Optimiser

Solar / Battery Charging Optimisation for Home Assistant

<h2>Pre-requisites</h2>

<h3>Home Assistant Octopus Energy Integration</h3>

[Github](https://github.com/BottlecapDave/HomeAssistant-OctopusEnergy)

<h3>Solcast Hobby Account</h>

[Here](https://solcast.com/free-rooftop-solar-forecasting?gclid=CjwKCAiAr4GgBhBFEiwAgwORrQp6co5Qw8zNjEgUhBee7Hfa39_baEWG-rB-GB3FFpiaIA5eAPHhahoC3vAQAvD_BwE)

<h3>Solcast PV Solar Integration</h3>

Still need a correct link for this

<h3>AppDaemon</h3>

1. Click the Home Assistant My button below to open the add-on on your Home Assistant instance:

https://camo.githubusercontent.com/c16bd5d7acfc6d5163636b546783e9217e27a401c1ac5bfd93a2ef5fa23e15fe/68747470733a2f2f6d792e686f6d652d617373697374616e742e696f2f6261646765732f73757065727669736f725f6164646f6e2e737667

[Link](https://my.home-assistant.io/redirect/supervisor_addon/?addon=a0d7b954_appdaemon&repository_url=https%3A%2F%2Fgithub.com%2Fhassio-addons%2Frepository)

2. Click on Install

3. Turn on Watchdog and Auto update

4. Click on Configuration at the top

5. Click the 3 dots and Edit in YAML:

   ```
   init_commands: []
   python_packages:
     - pandas
   system_packages: []

   ```

6. Go back to the Info page and click on Start

7. Click on Log. Appdaemon will download and install numpy and pandas. Click on Refresh until you see:

   ```
   INFO AppDaemon: Initializing app hello_world using class HelloWorld from module hello
   INFO hello_world: Hello from AppDaemon
   INFO hello_world: You are now ready to run Apps!
   INFO AppDaemon: App initialization complete
   INFO AppDaemon: New client Admin Client connected
   ```

Full documentaion can be found on the author's [Github page](https://github.com/hassio-addons/addon-appdaemon/blob/main/appdaemon/DOCS.md)
