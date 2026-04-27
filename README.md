# DevBuddy V1
## An engineer's assistant in development.
*DevBuddy is a project under development aimed to provide engineers with an easy platform to prototype embeeded systems.*

It provides vast options in voltages to be used to supply the target board, current consumption meassurements for all channels, serial communication options and lastly a PC app to monitor and control it.
Should be able to be used for the starting point of any custom testing rig

### File breakdown
* __DevBuddy_mk1__ - _Hardware files in KiCad_.
* __Scripts__ - _Python script for the PC app_.
* __dev_buddy_v1__ - _Firmware for the RP2350 MCU / Device_.
* __Resources__ - _You can find the current PCB schematic PDF and screenshots_.

### Current capabilities
* All communication is happening over UART
* Control digital outputs commanded by the APP
* Reading digital inputs commanded by the APP
* The device is capable of reporting back to the APP measurements of Voltages and Currents of 8 channels, with the ability to switch on or off the function as well as the intervals of the reporting
* The APP looks cool as hell!
* Added support for two 8-Bit DACs for APP and Device
* Added two controllable voltage channels on PCB, firmware will have to come later
* A first version of the dispatcher is operational
* There are three channels of UART communication available to the device and APP

![Alt text](https://github.com/ThanosPapad/dev_buddy/blob/main/Resources/Screenshots/DevBuddy_App_ADC_tab.png)

There are more screenshots in the folder showcasing the app

### Things that need to be done
* Software (I2C)for the variable voltage channels control
* The ability to record sessions of measuremnts, propably saved as CSV files
* The ability to choose analog channels and view the measurements in a graph would be quite cool as well
* The schematic should progressing quicker
* Need to figure out how the external channels will work, and If external I2C is needed as well
* Add ability for actions from external interrupts, that means one or two pins accessible to the user

More updates to come soon!
