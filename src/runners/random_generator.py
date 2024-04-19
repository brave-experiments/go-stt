import bentoml

class RandomGenerator(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("cpu")
    SUPPORTS_CPU_MULTI_THREADING = True
    
    def __init__(self):
        pass

    @bentoml.Runnable.method(batchable=False)
    def process(self, wav: str):
        return { "text" : str(len(wav)) + " " }
