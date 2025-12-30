"""
Graph Neural Network models for face classification.

Implements GAT (Graph Attention Network) for binary face classification:
- Class 0: Feature face (slots, pockets, steps, etc.)
- Class 1: Stock face (base material)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATv2Conv, global_mean_pool


class FaceClassificationGNN(nn.Module):
    """
    Graph Attention Network for face-level classification.

    Architecture:
    - 3 GATv2 layers with attention heads
    - BatchNorm + Dropout for regularization
    - Binary classification (feature vs stock)
    """

    def __init__(
        self,
        node_feature_dim: int = 12,
        edge_feature_dim: int = 2,
        hidden_dim: int = 64,
        num_layers: int = 3,
        num_heads: int = 4,
        dropout: float = 0.3,
        num_classes: int = 2
    ):
        """
        Initialize GNN model.

        Args:
            node_feature_dim: Dimension of node features
            edge_feature_dim: Dimension of edge features
            hidden_dim: Hidden layer dimension
            num_layers: Number of GAT layers
            num_heads: Number of attention heads
            dropout: Dropout probability
            num_classes: Number of output classes (2 for binary)
        """
        super().__init__()

        self.node_feature_dim = node_feature_dim
        self.edge_feature_dim = edge_feature_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.dropout = dropout
        self.num_classes = num_classes

        # Input projection
        self.input_proj = nn.Linear(node_feature_dim, hidden_dim)

        # GAT layers
        self.gat_layers = nn.ModuleList()
        self.batch_norms = nn.ModuleList()

        for i in range(num_layers):
            in_channels = hidden_dim if i == 0 else hidden_dim * num_heads

            # Last layer: single head for output
            heads = 1 if i == num_layers - 1 else num_heads

            gat = GATv2Conv(
                in_channels=in_channels,
                out_channels=hidden_dim,
                heads=heads,
                dropout=dropout,
                edge_dim=edge_feature_dim,
                concat=(i != num_layers - 1)  # Concat heads except last layer
            )

            self.gat_layers.append(gat)
            self.batch_norms.append(nn.BatchNorm1d(hidden_dim * heads if i != num_layers - 1 else hidden_dim))

        # Output classifier
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_classes)
        )

    def forward(self, data):
        """
        Forward pass.

        Args:
            data: PyTorch Geometric Data object with x, edge_index, edge_attr

        Returns:
            Node-level logits [num_nodes, num_classes]
        """
        x, edge_index, edge_attr = data.x, data.edge_index, data.edge_attr

        # Input projection
        x = self.input_proj(x)
        x = F.relu(x)

        # GAT layers
        for i, (gat, bn) in enumerate(zip(self.gat_layers, self.batch_norms)):
            x = gat(x, edge_index, edge_attr=edge_attr)
            x = bn(x)

            # ReLU except last layer
            if i < self.num_layers - 1:
                x = F.relu(x)
                x = F.dropout(x, p=self.dropout, training=self.training)

        # Classifier
        out = self.classifier(x)

        return out

    def predict(self, data):
        """
        Predict face labels.

        Args:
            data: PyTorch Geometric Data object

        Returns:
            Predicted labels [num_nodes]
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(data)
            preds = torch.argmax(logits, dim=1)
        return preds


class FaceClassificationGCN(nn.Module):
    """
    Simpler GCN baseline for comparison.

    Uses standard graph convolution instead of attention.
    """

    def __init__(
        self,
        node_feature_dim: int = 12,
        hidden_dim: int = 64,
        num_layers: int = 3,
        dropout: float = 0.3,
        num_classes: int = 2
    ):
        """Initialize GCN model."""
        super().__init__()

        from torch_geometric.nn import GCNConv

        self.node_feature_dim = node_feature_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout = dropout
        self.num_classes = num_classes

        # Input projection
        self.input_proj = nn.Linear(node_feature_dim, hidden_dim)

        # GCN layers
        self.gcn_layers = nn.ModuleList()
        self.batch_norms = nn.ModuleList()

        for i in range(num_layers):
            in_channels = hidden_dim

            gcn = GCNConv(in_channels, hidden_dim)
            self.gcn_layers.append(gcn)
            self.batch_norms.append(nn.BatchNorm1d(hidden_dim))

        # Output classifier
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_classes)
        )

    def forward(self, data):
        """Forward pass."""
        x, edge_index = data.x, data.edge_index

        # Input projection
        x = self.input_proj(x)
        x = F.relu(x)

        # GCN layers
        for i, (gcn, bn) in enumerate(zip(self.gcn_layers, self.batch_norms)):
            x = gcn(x, edge_index)
            x = bn(x)

            if i < self.num_layers - 1:
                x = F.relu(x)
                x = F.dropout(x, p=self.dropout, training=self.training)

        # Classifier
        out = self.classifier(x)

        return out

    def predict(self, data):
        """Predict face labels."""
        self.eval()
        with torch.no_grad():
            logits = self.forward(data)
            preds = torch.argmax(logits, dim=1)
        return preds
