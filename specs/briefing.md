`propeller-vision` is a console application to visualize the propeller loop.
To make this possible the program connects to the running propeller-engine 
via socket [protocol](https://raw.githubusercontent.com/thomasvolk/propeller-engine/refs/heads/main/docs/json-socket-interface.md).

The following commands are useful:

* `{"command": "status"}` - to check if the loop is running
* `{"command": "project"}` - returns the current and pending project data
* `{"type": "get_position"}` - to get the current position of the loop


