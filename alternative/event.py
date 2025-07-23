class Event:
    def __init__(self, time, action, priority, parameters=None):
        self.time = time
        self.action = action
        self.parameters = parameters
        self.priority = priority
