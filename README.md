# Platform for a Distributed Optimization Solver

Master's Thesis project.

TODO: explain how modular design and user can choose any solver but need some input and output requirements that it needs to follow! (maybe have this instead in a README.md file in solver folder, not sure...)



Document the message protocol and also on what format the problem data and solution data should be on in order for others to be able to solve and validate!


Uses python 3.12
sqlite3


Reference Swagger API documentation somehow? So users know how to interact with the server node web server? Or just say you can run the web server "python network.central_node_server" and then go to localhost:8000/docs to see the swagger documentation?

Experiments - use config.json file to share paths between the processes. Central node web server has a responsibility of creating the directories necessary for the experiments to run and then writes those paths to the config.json so agent nodes that start after the central node has started can get those paths...