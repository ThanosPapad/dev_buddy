# DevBuddy V1
## An engineer's assistant in development.
*DevBuddy is a project under development aimed to provide engineers with an easy platform to prototype embeeded systems.*

It provides vast options in voltages to be used to supply the target board, current consumption meassurements for all channels, serial communication options and lastly a PC app to monitor and control it.

### File breakdown
* __DevBuddy_mk1__ - _Hardware files in KiCad_.
* __Scripts__ - _Python script for the PC app_.
* __dev_buddy_v1__ - _Firmware for the RP2350 MCU / Device_.
* __Resources__ - _You can find the current PCB schematic and screenshots_.

### Current capabilities
* All communication is happening over UART
* Control digital outputs commanded by the APP
* Reading digital inputs commanded by the APP
* The device is capable of reporting back to the APP measurements of Voltages and Currents of 8 channels, with the ability to switch on or off the function as well as the intervals of the reporting
* The APP looks cool as hell!
* Added support for two 8-Bit DACs for APP and Device
* Added two controllable voltage channels on PCB, firmware will have to come later
![Alt text](Resources/screenshots/DevBuddy_App_ADC_tab.png)


### Things that need to be done
* Scheduling files creation and use so that predefined sequences can run easily
* Hardware and Software for the variable voltage channels control
* The ability to record sessions of measuremnts, propably saved as CSV files
* The ability to choose analog channels and view the measurements in a graph would be quite cool as well
* The schematic should progressing quicker

More updates to come soon!
