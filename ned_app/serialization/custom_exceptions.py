class DataFileLoadError(Exception):
 
    def __init__(self, value):
        self.value = value
 
    def __str__(self):
        return(repr(self.value))
    
class DataFileDeserializationError(Exception):
 
    def __init__(self, value):
        self.value = value
 
    def __str__(self):
        return(repr(self.value))