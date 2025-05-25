from concurrent import futures
import grpc
from embedding_pb2 import FloatListResponse, TextRequest
from embedding_pb2_grpc import EmbedServiceServicer, add_EmbedServiceServicer_to_server
import random
import torch
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import os

load_dotenv()

EMBEDDING = os.getenv('EMBEDDING', "BAAI/bge-base-en-v1.5")

embed_model = SentenceTransformer(EMBEDDING, device="cuda")

class EmbedServiceServicer(EmbedServiceServicer):
    def GetEmbedding(self, request, context):
        torch.cuda.empty_cache()
        embedding = embed_model.encode([request.text])[0]
        torch.cuda.empty_cache()
        return FloatListResponse(values=embedding)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_EmbedServiceServicer_to_server(EmbedServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    print("Starting gRPC embedding server on port 50051...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
