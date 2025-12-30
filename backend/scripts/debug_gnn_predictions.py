"""Debug GNN predictions to see if model is working correctly."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from app.testing.mfcad_loader import MFCADLoader
from app.core.topology.builder import AAGBuilder
from app.ml.graph_converter import AAGToGraphConverter
from app.ml.gnn_model import FaceClassificationGNN

# Load one test model
loader = MFCADLoader("/tmp/MFCAD/dataset/step")
test_ids = loader.get_all_model_ids()[:1000]
model_id = test_ids[700]  # First test model

print(f"Loading model: {model_id}")
model = loader.load_model(model_id)

# Build AAG
aag = AAGBuilder(model.shape).build()

# Convert to graph
converter = AAGToGraphConverter()
data = converter.convert(aag, face_labels=model.face_labels)

print(f"\nGraph info:")
print(f"  Nodes: {data.x.shape[0]}")
print(f"  Edges: {data.edge_index.shape[1]}")
print(f"  Node features: {data.x.shape[1]}")
print(f"  Labels: {data.y.unique()}")

# Load model
gnn = FaceClassificationGNN()
checkpoint = torch.load(Path(__file__).parent.parent / "models" / "gnn_face_classifier.pt", map_location='cpu')
gnn.load_state_dict(checkpoint['model_state_dict'])
gnn.eval()

# Run inference
with torch.no_grad():
    logits = gnn.forward(data)
    probs = torch.softmax(logits, dim=1)
    preds = torch.argmax(logits, dim=1)

print(f"\nPredictions:")
print(f"  Class 0 (feature): {(preds == 0).sum().item()}/{len(preds)}")
print(f"  Class 1 (stock):   {(preds == 1).sum().item()}/{len(preds)}")

print(f"\nGround truth (from labels):")
print(f"  Class 0 (feature): {(data.y == 0).sum().item()}/{len(data.y)}")
print(f"  Class 1 (stock):   {(data.y == 1).sum().item()}/{len(data.y)}")

print(f"\nSample predictions (first 10):")
for i in range(min(10, len(preds))):
    print(f"  Face {i}: pred={preds[i].item()} (prob={probs[i, preds[i]].item():.3f}), true={data.y[i].item()}")

print(f"\nLogits statistics:")
print(f"  Class 0 logits: mean={logits[:, 0].mean():.3f}, std={logits[:, 0].std():.3f}")
print(f"  Class 1 logits: mean={logits[:, 1].mean():.3f}, std={logits[:, 1].std():.3f}")
