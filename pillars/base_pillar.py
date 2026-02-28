class BasePillar:

    def __init__(self, country, provider):
        self.country = country
        self.provider = provider
        self.score = None

    def fetch_data(self):
        pass

    def calculate(self):
        pass

    def run(self):
        self.fetch_data()
        self.calculate()
        return self.score