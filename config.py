import os

class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:123456@localhost:27017/dennis?authSource=admin")
