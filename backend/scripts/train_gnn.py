#!/usr/bin/env python3
"""
Train GNN for face classification on MFCAD dataset.

Binary classification: feature face (0) vs stock face (1)
"""

import sys
import logging
from pathlib import Path
import torch
import torch.nn.functional as F
from torch_geometric.loader import DataLoader
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.mfcad_dataset import MFCADGraphDataset
from app.ml.gnn_model import FaceClassificationGNN, FaceClassificationGCN

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_epoch(model, loader, optimizer, device):
    """Train for one epoch."""
    model.train()

    total_loss = 0
    total_correct = 0
    total_samples = 0

    for batch in loader:
        batch = batch.to(device)

        optimizer.zero_grad()

        # Forward pass
        out = model(batch)

        # Only compute loss on labeled nodes (y != -1)
        mask = batch.y != -1
        if mask.sum() == 0:
            continue

        loss = F.cross_entropy(out[mask], batch.y[mask])

        # Backward pass
        loss.backward()
        optimizer.step()

        # Statistics
        total_loss += loss.item() * mask.sum().item()
        pred = out[mask].argmax(dim=1)
        total_correct += (pred == batch.y[mask]).sum().item()
        total_samples += mask.sum().item()

    avg_loss = total_loss / total_samples if total_samples > 0 else 0
    accuracy = total_correct / total_samples if total_samples > 0 else 0

    return avg_loss, accuracy


@torch.no_grad()
def evaluate(model, loader, device):
    """Evaluate model."""
    model.eval()

    total_loss = 0
    total_correct = 0
    total_samples = 0

    # Confusion matrix
    tp, fp, tn, fn = 0, 0, 0, 0

    for batch in loader:
        batch = batch.to(device)

        # Forward pass
        out = model(batch)

        # Only evaluate labeled nodes
        mask = batch.y != -1
        if mask.sum() == 0:
            continue

        loss = F.cross_entropy(out[mask], batch.y[mask])

        # Statistics
        total_loss += loss.item() * mask.sum().item()
        pred = out[mask].argmax(dim=1)
        labels = batch.y[mask]

        total_correct += (pred == labels).sum().item()
        total_samples += mask.sum().item()

        # Confusion matrix (0=feature, 1=stock)
        tp += ((pred == 0) & (labels == 0)).sum().item()
        fp += ((pred == 0) & (labels == 1)).sum().item()
        tn += ((pred == 1) & (labels == 1)).sum().item()
        fn += ((pred == 1) & (labels == 0)).sum().item()

    avg_loss = total_loss / total_samples if total_samples > 0 else 0
    accuracy = total_correct / total_samples if total_samples > 0 else 0

    # Precision, recall, F1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'loss': avg_loss,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'tp': tp,
        'fp': fp,
        'tn': tn,
        'fn': fn
    }


def main():
    """Train GNN on MFCAD dataset."""

    logger.info("=" * 80)
    logger.info("GNN TRAINING ON MFCAD DATASET")
    logger.info("=" * 80)

    # Hyperparameters
    BATCH_SIZE = 8
    EPOCHS = 50
    LEARNING_RATE = 0.001
    HIDDEN_DIM = 64
    NUM_LAYERS = 3
    NUM_HEADS = 4
    DROPOUT = 0.3
    SAMPLE_SIZE = 1000  # Use 1000 models for faster training

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Using device: {device}")

    # Load dataset
    logger.info("\n1. Loading MFCAD dataset...")
    dataset = MFCADGraphDataset(dataset_path="/tmp/MFCAD/dataset/step")

    # Create stratified sample
    logger.info(f"2. Creating sample of {SAMPLE_SIZE} models...")
    all_model_ids = dataset.loader.create_stratified_sample(n_samples=SAMPLE_SIZE, seed=42)
    dataset.model_ids = all_model_ids

    # Train/test split
    logger.info("3. Splitting dataset (70% train, 30% test)...")
    train_dataset, test_dataset = dataset.get_train_test_split(train_ratio=0.7, seed=42)

    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

    logger.info(f"   Train: {len(train_dataset)} models")
    logger.info(f"   Test: {len(test_dataset)} models")

    # Initialize model
    logger.info("\n4. Initializing GNN model...")
    logger.info(f"   Architecture: GAT with {NUM_LAYERS} layers, {NUM_HEADS} heads")
    logger.info(f"   Hidden dim: {HIDDEN_DIM}, Dropout: {DROPOUT}")

    model = FaceClassificationGNN(
        node_feature_dim=12,
        edge_feature_dim=2,
        hidden_dim=HIDDEN_DIM,
        num_layers=NUM_LAYERS,
        num_heads=NUM_HEADS,
        dropout=DROPOUT,
        num_classes=2
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"   Total parameters: {total_params:,}")

    # Optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=5e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='max', factor=0.5, patience=5
    )

    # Training loop
    logger.info(f"\n5. Training for {EPOCHS} epochs...")
    logger.info("=" * 80)

    best_test_f1 = 0
    best_epoch = 0

    for epoch in range(1, EPOCHS + 1):
        # Train
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, device)

        # Evaluate
        test_metrics = evaluate(model, test_loader, device)

        # Update learning rate
        scheduler.step(test_metrics['f1'])

        # Log
        logger.info(
            f"Epoch {epoch:3d} | "
            f"Train Loss: {train_loss:.4f} Acc: {train_acc:.3f} | "
            f"Test Loss: {test_metrics['loss']:.4f} Acc: {test_metrics['accuracy']:.3f} "
            f"F1: {test_metrics['f1']:.3f}"
        )

        # Save best model
        if test_metrics['f1'] > best_test_f1:
            best_test_f1 = test_metrics['f1']
            best_epoch = epoch

            # Save model
            model_path = Path(__file__).parent.parent / "models" / "gnn_face_classifier.pt"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'test_f1': best_test_f1,
                'test_accuracy': test_metrics['accuracy'],
            }, model_path)

            logger.info(f"   ✓ Saved best model (F1: {best_test_f1:.3f})")

    # Final evaluation
    logger.info("\n" + "=" * 80)
    logger.info("FINAL RESULTS")
    logger.info("=" * 80)

    final_metrics = evaluate(model, test_loader, device)

    logger.info(f"Test Accuracy: {final_metrics['accuracy']:.2%}")
    logger.info(f"Test Precision: {final_metrics['precision']:.2%}")
    logger.info(f"Test Recall: {final_metrics['recall']:.2%}")
    logger.info(f"Test F1 Score: {final_metrics['f1']:.2%}")

    logger.info(f"\nConfusion Matrix:")
    logger.info(f"  TP (correct feature): {final_metrics['tp']}")
    logger.info(f"  FP (stock as feature): {final_metrics['fp']}")
    logger.info(f"  TN (correct stock): {final_metrics['tn']}")
    logger.info(f"  FN (feature as stock): {final_metrics['fn']}")

    logger.info(f"\nBest model saved from epoch {best_epoch}")
    logger.info(f"Best test F1: {best_test_f1:.2%}")

    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    main()
