import chromadb
client = chromadb.Client()
class DummyChromaEmbedder:
    name = "dummy"
    def __call__(self, input: list) -> list:
        return [[0.1] * 384 for _ in input]
try:
    collection = client.create_collection("test", embedding_function=DummyChromaEmbedder())
    collection.add(ids=["1"], documents=["hello"], embeddings=[[0.1]*384])
    print("SUCCESS")
except Exception as e:
    print("EXCEPTION:", repr(e))
