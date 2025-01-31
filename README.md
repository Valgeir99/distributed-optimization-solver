# Platform for a Distributed Optimization Solver

Master's Thesis project.

TODO: explain how modular design and user can choose any solver but need some input and output requirements that it needs to follow! (maybe have this instead in a README.md file in solver folder, not sure...)

Explain difference between central_node.py and central_node_server.py (central node is just the functions of the node while the server file creates a central node object and starts a web server that the central node manages the data and resources of, allows agent to communicate with the server node)


Document the message protocol and also on what format the problem data and solution data should be on in order for others to be able to solve and validate!


Uses python 3.12
sqlite3

Need to add problem instances to data/miplib_problem_instances and then insert them into the database table 'problem_instances' in data/data.sql in order to use these problem instances on the platform!


Reference Swagger API documentation somehow? So users know how to interact with the server node web server? Or just say you can run the web server "python network.central_node_server" and then go to localhost:8000/docs to see the swagger documentation?

Experiments - use config.json file to share paths between the processes. Central node web server has a responsibility of creating the directories necessary for the experiments to run and then writes those paths to the config.json so agent nodes that start after the central node has started can get those paths...

Give good instructions how to start experiments using this code!!