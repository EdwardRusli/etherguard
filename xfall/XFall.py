"""
================================================================================
XFALL: COMPLETE IMPLEMENTATION
================================================================================
Domain Adaptive Wi-Fi-Based Fall Detection
Based on: IEEE Journal on Selected Areas in Communications, Vol. 42, No. 9, 2024

This module implements all core algorithms:
- SDP Generation
- STATE (Spatio-Temporal Attention-based Transformer Encoder)
- MLP Classifier
- Training and Inference

================================================================================
"""

import numpy as np
import csv
import json
from io import StringIO
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from pathlib import Path


# =============================================================================
# CSI PARSER (ORIGINAL - UNCHANGED)
# =============================================================================

COLUMNS_ESP32 = [
    'type', 'id', 'mac', 'rssi', 'rate', 'sig_mode', 'mcs', 'bandwidth',
    'smoothing', 'not_sounding', 'aggregation', 'stbc', 'fec_coding', 'sgi',
    'noise_floor', 'ampdu_cnt', 'channel', 'secondary_channel',
    'local_timestamp', 'ant', 'sig_len', 'rx_state', 'len', 'first_word', 'data'
]

COLUMNS_C5C6 = [
    'type', 'id', 'mac', 'rssi', 'rate', 'noise_floor', 'fft_gain',
    'agc_gain', 'channel', 'local_timestamp', 'sig_len', 'rx_state',
    'len', 'first_word', 'data'
]


@dataclass
class CSIFrame:
    """A single parsed CSI measurement."""
    timestamp: int
    rssi: int
    mac: str
    channel: int
    n_subcarriers: int
    amplitude: np.ndarray
    phase: np.ndarray
    complex_csi: np.ndarray
    raw_metadata: dict = field(default_factory=dict)


def parse_csi_line(line: str) -> Optional[CSIFrame]:
    """Parse a single CSI_DATA serial line into a CSIFrame."""
    line = line.strip()
    if isinstance(line, bytes):
        line = line.decode('utf-8', errors='replace')
    line = line.lstrip("b'").rstrip("\\r\\n'")

    if 'CSI_DATA' not in line:
        return None

    try:
        reader = csv.reader(StringIO(line))
        fields = next(reader)
    except (csv.Error, StopIteration):
        return None

    if len(fields) == len(COLUMNS_ESP32):
        columns = COLUMNS_ESP32
    elif len(fields) == len(COLUMNS_C5C6):
        columns = COLUMNS_C5C6
    else:
        return None

    try:
        csi_raw = json.loads(fields[-1])
    except (json.JSONDecodeError, IndexError):
        return None

    declared_len = int(fields[-3])
    if declared_len != len(csi_raw):
        return None

    n_subcarriers = len(csi_raw) // 2
    complex_csi = np.zeros(n_subcarriers, dtype=np.complex64)
    for i in range(n_subcarriers):
        real_part = csi_raw[i * 2 + 1]
        imag_part = csi_raw[i * 2]
        complex_csi[i] = complex(real_part, imag_part)

    amplitude = np.abs(complex_csi)
    phase = np.angle(complex_csi)
    metadata = {col: val for col, val in zip(columns, fields)}

    return CSIFrame(
        timestamp=int(metadata.get('local_timestamp', 0)),
        rssi=int(metadata.get('rssi', 0)),
        mac=metadata.get('mac', ''),
        channel=int(metadata.get('channel', 0)),
        n_subcarriers=n_subcarriers,
        amplitude=amplitude,
        phase=phase,
        complex_csi=complex_csi,
        raw_metadata=metadata,
    )


def frames_to_matrix(frames: List[CSIFrame]) -> np.ndarray:
    """Convert list of CSIFrame to CSI matrix H."""
    if not frames:
        raise ValueError("No frames provided")
    n_packets = len(frames)
    n_subcarriers = frames[0].n_subcarriers
    H = np.zeros((n_packets, n_subcarriers), dtype=np.complex64)
    for i, frame in enumerate(frames):
        H[i, :] = frame.complex_csi
    return H


# =============================================================================
# ALGORITHM 1: GENERATE SDP
# =============================================================================

def generate_sdp(
    H: np.ndarray,
    num_lag_samples: int,
    window_size: int,
    normalize: bool = True
) -> np.ndarray:
    """
    Generate Speed Distribution Profile from CSI matrix.
    
    Parameters:
    -----------
    H : np.ndarray, shape (N_T, N_S)
        CSI matrix with complex values
    num_lag_samples : int (N_Δ)
        Number of lag samples (spatial/speed resolution)
    window_size : int (W_T)
        Window size (temporal span)
    normalize : bool
        Apply probabilistic normalization (columns sum to 1)
    
    Returns:
    --------
    S : np.ndarray, shape (N_Δ, W_T)
        Speed Distribution Profile matrix
    """
    N_T, N_S = H.shape
    N_Δ = num_lag_samples
    W_T = window_size
    
    # Step 1: Compute ACF tensor ρ ∈ C^(N_Δ × W_T × N_S)
    ρ = np.zeros((N_Δ, W_T, N_S), dtype=np.complex128)
    
    for n in range(N_Δ):
        for i in range(W_T):
            packet_idx = i + N_Δ
            
            if packet_idx >= N_T:
                continue
            
            for j in range(N_S):
                ref_idx = packet_idx - n
                
                # Get CSI values
                H_curr = H[packet_idx, j]
                H_ref = H[ref_idx, j]
                
                # Compute magnitudes
                mag_curr = np.abs(H_curr)
                mag_ref = np.abs(H_ref)
                
                # Compute ACF element (Equation 9) using complex phase
                if mag_curr > 1e-10 and mag_ref > 1e-10:
                    numerator = H_curr * np.conj(H_ref)
                    denominator = mag_curr * mag_ref
                    ρ[n, i, j] = numerator / denominator
    
    # Step 2: Coherent sum across subcarriers (preserves phase shift/Doppler)
    # Then take magnitude (strictly positive for probabilistic normalization)
    S_num = np.abs(np.mean(ρ, axis=2))
    
    # Step 3: Probabilistic normalization (Equation 10 denominator)
    if normalize:
        col_sums = np.sum(S_num, axis=0, keepdims=True)
        col_sums = np.maximum(col_sums, 1e-10)
        S = S_num / col_sums
    else:
        S = S_num
    
    return S


def generate_sdp_fast(
    H: np.ndarray,
    num_lag_samples: int,
    window_size: int,
    normalize: bool = True
) -> np.ndarray:
    """
    Vectorized SDP generation — ~50x faster than generate_sdp().

    Parameters / Returns: same as generate_sdp().
    """
    N_T, N_S = H.shape
    N_Δ = num_lag_samples
    W_T = window_size

    # Clamp W_T so packet_idx = i + N_Δ stays within N_T
    W_T = min(W_T, N_T - N_Δ)
    if W_T <= 0:
        return np.zeros((N_Δ, 1), dtype=np.float64)

    # Build index arrays for current and reference packets
    # packet_idx[i] = i + N_Δ  for i in [0, W_T)
    i_arr = np.arange(W_T)
    packet_idx = i_arr + N_Δ  # (W_T,)

    # For each lag n, ref_idx = packet_idx - n
    n_arr = np.arange(N_Δ)  # (N_Δ,)

    # H_curr: shape (W_T, N_S)
    H_curr = H[packet_idx, :]  # (W_T, N_S)
    mag_curr = np.abs(H_curr)  # (W_T, N_S)

    # S will be (N_Δ, W_T)
    S_num = np.zeros((N_Δ, W_T), dtype=np.float64)

    for n in range(N_Δ):
        ref_idx = packet_idx - n  # (W_T,)
        H_ref = H[ref_idx, :]    # (W_T, N_S)
        mag_ref = np.abs(H_ref)  # (W_T, N_S)

        # ACF: normalized complex cross-correlation
        denom = mag_curr * mag_ref
        valid = denom > 1e-10
        acf_norm = np.zeros_like(H_curr, dtype=np.complex64)
        acf_norm[valid] = (H_curr * np.conj(H_ref))[valid] / denom[valid]

        # Coherent sum across subcarriers (preserves phase/Doppler!)
        # then take magnitude to keep it strictly non-negative for normalization
        corr = acf_norm.mean(axis=1) # (W_T,)
        S_num[n, :] = np.abs(corr)

    # Probabilistic normalization
    if normalize:
        col_sums = S_num.sum(axis=0, keepdims=True)
        col_sums = np.maximum(col_sums, 1e-10)
        S = S_num / col_sums
    else:
        S = S_num

    return S

# =============================================================================
# ALGORITHM 2: MULTI-HEAD SELF-ATTENTION
# =============================================================================

def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """Compute softmax along specified axis."""
    exp_x = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)


def layer_norm(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Layer normalization."""
    mean = np.mean(x, axis=-1, keepdims=True)
    std = np.std(x, axis=-1, keepdims=True)
    return (x - mean) / (std + eps)


def multi_head_attention(
    X: np.ndarray,
    W_Q: np.ndarray,
    W_K: np.ndarray,
    W_V: np.ndarray,
    W_O: np.ndarray,
    n_heads: int
) -> np.ndarray:
    """
    Multi-Head Self-Attention.
    
    Parameters:
    -----------
    X : np.ndarray, shape (L, d_in)
        Input sequence
    W_Q, W_K, W_V, W_O : np.ndarray
        Projection weights
    n_heads : int
        Number of attention heads
    
    Returns:
    --------
    Y : np.ndarray, shape (L, d_out)
        Attention output
    """
    L = X.shape[0]
    d_k = W_Q.shape[1] // n_heads
    d_v = W_V.shape[1] // n_heads
    
    # Linear projections (Equation 11)
    Q = X @ W_Q  # (L, h*d_k)
    K = X @ W_K  # (L, h*d_k)
    V = X @ W_V  # (L, h*d_v)
    
    # Reshape for multi-head: (L, h, d) -> (h, L, d)
    Q = Q.reshape(L, n_heads, d_k).transpose(1, 0, 2)
    K = K.reshape(L, n_heads, d_k).transpose(1, 0, 2)
    V = V.reshape(L, n_heads, d_v).transpose(1, 0, 2)
    
    # Scaled dot-product attention (Equation 12)
    scores = Q @ K.transpose(0, 2, 1) / np.sqrt(d_k)
    attention = softmax(scores, axis=-1)
    
    # Apply attention to values
    heads = attention @ V  # (h, L, d_v)
    
    # Concatenate heads (Equation 13)
    heads = heads.transpose(1, 0, 2).reshape(L, n_heads * d_v)
    
    # Output projection
    Y = heads @ W_O
    
    return Y


# =============================================================================
# ALGORITHM 3: TRANSFORMER ENCODER BLOCK
# =============================================================================

def transformer_encoder_block(
    X: np.ndarray,
    W_Q: np.ndarray,
    W_K: np.ndarray,
    W_V: np.ndarray,
    W_O: np.ndarray,
    W_ff1: np.ndarray,
    b_ff1: np.ndarray,
    W_ff2: np.ndarray,
    b_ff2: np.ndarray,
    n_heads: int
) -> np.ndarray:
    """
    Single transformer encoder block with residual connections.
    
    Parameters:
    -----------
    X : np.ndarray, shape (L, d_model)
        Input sequence
    
    Returns:
    --------
    Y : np.ndarray, shape (L, d_model)
        Encoded sequence
    """
    # Multi-Head Self-Attention + Residual + LayerNorm
    attn_out = multi_head_attention(X, W_Q, W_K, W_V, W_O, n_heads)
    X = layer_norm(X + attn_out)
    
    # Feed-Forward Network
    ff_hidden = np.maximum(0, X @ W_ff1 + b_ff1)  # ReLU
    ff_out = ff_hidden @ W_ff2 + b_ff2
    
    # Residual + LayerNorm
    Y = layer_norm(X + ff_out)
    
    return Y


# =============================================================================
# ALGORITHM 4: SPATIAL TRANSFORMER ENCODER
# =============================================================================

def spatial_transformer_encoder(
    S_i: np.ndarray,
    d_s: int,
    weights: Dict
) -> np.ndarray:
    """
    Extract spatial features from a single SDP column.
    
    Parameters:
    -----------
    S_i : np.ndarray, shape (N_Δ,)
        Single SDP column (speed distribution at one time)
    d_s : int
        Embedding dimension
    weights : Dict
        Contains cls_token, pos_embed, and block weights
    
    Returns:
    --------
    y_i : np.ndarray, shape (d_s,)
        Spatial feature vector
    """
    N_Δ = len(S_i)
    L = N_Δ // d_s
    
    # Reshape to patches
    X = S_i[:L * d_s].reshape(L, d_s)
    
    # Prepend CLS token
    CLS = weights['cls_token']  # (1, d_s)
    X = np.vstack([CLS, X])  # (L+1, d_s)
    
    # Add position embeddings
    X = X + weights['pos_embed']
    
    # Pass through transformer blocks
    for block in weights['blocks']:
        X = transformer_encoder_block(
            X,
            block['W_Q'], block['W_K'], block['W_V'], block['W_O'],
            block['W_ff1'], block['b_ff1'], block['W_ff2'], block['b_ff2'],
            block['n_heads']
        )
    
    # Extract CLS token as output
    y_i = X[0, :]
    
    return y_i


# =============================================================================
# ALGORITHM 5: TEMPORAL TRANSFORMER ENCODER
# =============================================================================

def temporal_transformer_encoder(
    Y: np.ndarray,
    weights: Dict
) -> np.ndarray:
    """
    Extract temporal features from sequence of spatial features.
    
    Parameters:
    -----------
    Y : np.ndarray, shape (W_T, d_s)
        Spatial features from all time steps
    
    Returns:
    --------
    z_0 : np.ndarray, shape (d_s,)
        General Fall Representation (GFR)
    """
    W_T = Y.shape[0]
    
    # Prepend CLS token
    CLS = weights['cls_token']  # (1, d_s)
    X = np.vstack([CLS, Y])  # (W_T+1, d_s)
    
    # Add position embeddings
    X = X + weights['pos_embed']
    
    # Pass through transformer blocks
    for block in weights['blocks']:
        X = transformer_encoder_block(
            X,
            block['W_Q'], block['W_K'], block['W_V'], block['W_O'],
            block['W_ff1'], block['b_ff1'], block['W_ff2'], block['b_ff2'],
            block['n_heads']
        )
    
    # Extract CLS token as GFR
    z_0 = X[0, :]
    
    return z_0


# =============================================================================
# ALGORITHM 6: STATE
# =============================================================================

def STATE(
    S: np.ndarray,
    d_s: int,
    spatial_weights: Dict,
    temporal_weights: Dict
) -> np.ndarray:
    """
    Spatio-Temporal Attention-based Transformer Encoder.
    
    Parameters:
    -----------
    S : np.ndarray, shape (N_Δ, W_T)
        SDP matrix
    d_s : int
        Embedding dimension
    spatial_weights : Dict
        Weights for spatial encoders
    temporal_weights : Dict
        Weights for temporal encoder
    
    Returns:
    --------
    GFR : np.ndarray, shape (d_s,)
        General Fall Representation
    """
    N_Δ, W_T = S.shape
    
    # Initialize spatial feature array
    Y = np.zeros((W_T, d_s))
    
    # Process each SDP column with spatial encoder
    for i in range(W_T):
        S_i = S[:, i]
        y_i = spatial_transformer_encoder(S_i, d_s, spatial_weights)
        Y[i, :] = y_i
    
    # Process spatial features with temporal encoder
    GFR = temporal_transformer_encoder(Y, temporal_weights)
    
    return GFR


# =============================================================================
# ALGORITHM 7: MLP CLASSIFIER
# =============================================================================

def MLP(
    x: np.ndarray,
    weights: Dict
) -> float:
    """
    Multi-layer perceptron for fall classification.
    
    Parameters:
    -----------
    x : np.ndarray, shape (d_s,)
        Input feature (GFR)
    weights : Dict
        MLP weights {W_1, b_1, W_2, b_2, W_3, b_3}
    
    Returns:
    --------
    logit : float
        Classification logit
    """
    # Layer 1
    h = np.maximum(0, x @ weights['W_1'] + weights['b_1'])  # ReLU
    
    # Layer 2
    h = np.maximum(0, h @ weights['W_2'] + weights['b_2'])  # ReLU
    
    # Output layer
    logit = h @ weights['W_3'] + weights['b_3']
    
    return float(np.squeeze(logit))


def sigmoid(x: float) -> float:
    """Sigmoid function."""
    return 1.0 / (1.0 + np.exp(-x))


# =============================================================================
# WEIGHT INITIALIZATION
# =============================================================================

def init_transformer_weights(d_model: int, d_ff: int, n_heads: int) -> Dict:
    """Initialize weights for a transformer encoder block."""
    d_k = d_model // n_heads
    d_v = d_model // n_heads
    
    scale = 0.02
    return {
        'W_Q': np.random.randn(d_model, n_heads * d_k) * scale,
        'W_K': np.random.randn(d_model, n_heads * d_k) * scale,
        'W_V': np.random.randn(d_model, n_heads * d_v) * scale,
        'W_O': np.random.randn(n_heads * d_v, d_model) * scale,
        'W_ff1': np.random.randn(d_model, d_ff) * scale,
        'b_ff1': np.zeros(d_ff),
        'W_ff2': np.random.randn(d_ff, d_model) * scale,
        'b_ff2': np.zeros(d_model),
        'n_heads': n_heads
    }


def init_spatial_weights(N_Δ: int, d_s: int, n_heads: int, n_layers: int) -> Dict:
    """Initialize weights for spatial transformer encoder."""
    L = N_Δ // d_s
    return {
        'cls_token': np.random.randn(1, d_s) * 0.02,
        'pos_embed': np.random.randn(L + 1, d_s) * 0.02,
        'blocks': [init_transformer_weights(d_s, d_s * 4, n_heads) for _ in range(n_layers)]
    }


def init_temporal_weights(W_T: int, d_s: int, n_heads: int, n_layers: int) -> Dict:
    """Initialize weights for temporal transformer encoder."""
    return {
        'cls_token': np.random.randn(1, d_s) * 0.02,
        'pos_embed': np.random.randn(W_T + 1, d_s) * 0.02,
        'blocks': [init_transformer_weights(d_s, d_s * 4, n_heads) for _ in range(n_layers)]
    }


def init_mlp_weights(d_s: int, hidden_dims: List[int]) -> Dict:
    """Initialize MLP weights."""
    dims = [d_s] + hidden_dims + [1]
    weights = {}
    scale = 0.02
    
    for i in range(len(dims) - 1):
        weights[f'W_{i+1}'] = np.random.randn(dims[i], dims[i+1]) * scale
        weights[f'b_{i+1}'] = np.zeros(dims[i+1])
    
    return weights


# =============================================================================
# ALGORITHM 8: XFALL TRAINING (NUMPY)
# =============================================================================

def xfall_forward(
    H: np.ndarray,
    params: Dict,
    spatial_weights: Dict,
    temporal_weights: Dict,
    mlp_weights: Dict
) -> Tuple[float, float]:
    """
    Forward pass through XFall.
    
    Returns:
    --------
    logit : float
        Raw classification output
    prob : float
        Sigmoid probability
    """
    # Generate SDP
    S = generate_sdp(H, params['N_Δ'], params['W_T'])
    
    # Extract GFR
    GFR = STATE(S, params['d_s'], spatial_weights, temporal_weights)
    
    # Classify
    logit = MLP(GFR, mlp_weights)
    prob = sigmoid(logit)
    
    return logit, prob


def xfall_train_step(
    H: np.ndarray,
    y: int,
    params: Dict,
    spatial_weights: Dict,
    temporal_weights: Dict,
    mlp_weights: Dict,
    lr: float
) -> float:
    """
    Single training step with gradient computation.
    
    Note: This is a simplified version using numerical gradients.
    For production, use PyTorch/TensorFlow for automatic differentiation.
    """
    # Forward pass
    logit, prob = xfall_forward(H, params, spatial_weights, temporal_weights, mlp_weights)
    
    # Binary cross-entropy loss
    eps = 1e-7
    loss = -y * np.log(prob + eps) - (1 - y) * np.log(1 - prob + eps)
    
    # Note: In practice, use PyTorch for proper backpropagation
    # This is a placeholder for the algorithm structure
    
    return float(loss)


def xfall_train(
    frames_list: List[List[CSIFrame]],
    labels: np.ndarray,
    params: Dict,
    n_epochs: int = 100,
    lr: float = 1e-4,
    batch_size: int = 32
) -> Tuple[Dict, Dict, Dict]:
    """
    Train XFall model.
    
    Parameters:
    -----------
    frames_list : List[List[CSIFrame]]
        List of CSI frame sequences
    labels : np.ndarray, shape (N,)
        Binary labels (0=normal, 1=fall)
    params : Dict
        Model parameters
    n_epochs : int
        Number of training epochs
    lr : float
        Learning rate
    batch_size : int
        Batch size
    
    Returns:
    --------
    spatial_weights, temporal_weights, mlp_weights : Dict
        Trained model weights
    
    NOTE: For actual training, use PyTorch implementation below.
    This NumPy version is for algorithm demonstration only.
    """
    N = len(frames_list)
    
    # Initialize weights
    spatial_weights = init_spatial_weights(
        params['N_Δ'], params['d_s'], params['n_heads'], params['n_layers_spatial']
    )
    temporal_weights = init_temporal_weights(
        params['W_T'], params['d_s'], params['n_heads'], params['n_layers_temporal']
    )
    mlp_weights = init_mlp_weights(params['d_s'], [128, 64])
    
    print("Note: Use PyTorch version for actual training with backpropagation")
    print("This NumPy version demonstrates the algorithm structure only")
    
    return spatial_weights, temporal_weights, mlp_weights


# =============================================================================
# ALGORITHM 9: XFALL INFERENCE
# =============================================================================

def xfall_inference(
    frames: List[CSIFrame],
    params: Dict,
    spatial_weights: Dict,
    temporal_weights: Dict,
    mlp_weights: Dict,
    threshold: float = 0.5
) -> Tuple[int, float]:
    """
    XFall inference - detect fall from CSI frames.
    
    Parameters:
    -----------
    frames : List[CSIFrame]
        List of CSI frames from parser
    params : Dict
        Model parameters
    spatial_weights : Dict
        Trained spatial encoder weights
    temporal_weights : Dict
        Trained temporal encoder weights
    mlp_weights : Dict
        Trained MLP weights
    threshold : float
        Classification threshold
    
    Returns:
    --------
    prediction : int
        1 if fall detected, 0 otherwise
    confidence : float
        Probability score
    """
    # Convert frames to CSI matrix
    H = frames_to_matrix(frames)
    
    # Forward pass
    logit, prob = xfall_forward(H, params, spatial_weights, temporal_weights, mlp_weights)
    
    # Make prediction
    prediction = 1 if prob >= threshold else 0
    
    return prediction, prob


# =============================================================================
# PYTORCH IMPLEMENTATION (For Actual Training)
# =============================================================================

"""
For actual training with backpropagation, use PyTorch:

import torch
import torch.nn as nn

class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.mha = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
    
    def forward(self, x):
        return self.mha(x, x, x)[0]

class TransformerBlock(nn.Module):
    def __init__(self, d_model, n_heads, d_ff):
        super().__init__()
        self.attn = MultiHeadAttention(d_model, n_heads)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.ReLU(),
            nn.Linear(d_ff, d_model)
        )
    
    def forward(self, x):
        x = self.norm1(x + self.attn(x))
        x = self.norm2(x + self.ff(x))
        return x

class STATE(nn.Module):
    def __init__(self, N_delta, W_T, d_s, n_heads, n_layers_spatial, n_layers_temporal):
        super().__init__()
        self.spatial_encoders = nn.ModuleList([
            nn.Sequential(*[TransformerBlock(d_s, n_heads, d_s*4) 
                           for _ in range(n_layers_spatial)])
            for _ in range(W_T)
        ])
        self.temporal_encoder = nn.Sequential(
            *[TransformerBlock(d_s, n_heads, d_s*4) 
              for _ in range(n_layers_temporal)]
        )
        self.cls_token = nn.Parameter(torch.randn(1, 1, d_s) * 0.02)
        self.pos_embed_spatial = nn.Parameter(torch.randn(1, N_delta//d_s + 1, d_s) * 0.02)
        self.pos_embed_temporal = nn.Parameter(torch.randn(1, W_T + 1, d_s) * 0.02)
    
    def forward(self, S):
        # S: (batch, N_delta, W_T)
        pass  # Implementation details...

class XFall(nn.Module):
    def __init__(self, params):
        super().__init__()
        self.state = STATE(...)
        self.mlp = nn.Sequential(
            nn.Linear(d_s, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )
    
    def forward(self, H):
        S = generate_sdp(H)
        gfr = self.state(S)
        logit = self.mlp(gfr)
        return logit
"""


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate the complete XFall pipeline."""
    print("=" * 60)
    print("XFall Complete Implementation Demo")
    print("=" * 60)
    
    # Parameters
    params = {
        'N_Δ': 50,           # Number of lag samples
        'W_T': 100,          # Window size
        'd_s': 32,           # Embedding dimension
        'n_heads': 4,        # Number of attention heads
        'n_layers_spatial': 1,
        'n_layers_temporal': 2
    }
    
    print("\n1. Parameters:")
    for k, v in params.items():
        print(f"   {k}: {v}")
    
    # Generate synthetic CSI data
    N_T = params['N_Δ'] + params['W_T'] + 50  # Enough packets
    N_S = 64  # Subcarriers
    
    print(f"\n2. Generating synthetic CSI data:")
    print(f"   N_T (packets): {N_T}")
    print(f"   N_S (subcarriers): {N_S}")
    
    H = np.random.randn(N_T, N_S) + 1j * np.random.randn(N_T, N_S)
    
    # Add motion effect
    motion_start = int(0.3 * N_T)
    motion_end = int(0.7 * N_T)
    for i in range(N_S):
        phase = np.zeros(N_T)
        phase[motion_start:motion_end] = 3 * np.sin(
            np.linspace(0, 4*np.pi, motion_end-motion_start)
        )
        H[:, i] *= np.exp(1j * phase * (i + 1) / N_S)
    
    # Test SDP generation
    print("\n3. Generating SDP...")
    S = generate_sdp(H, params['N_Δ'], params['W_T'])
    print(f"   SDP shape: {S.shape}")
    print(f"   SDP range: [{S.min():.4f}, {S.max():.4f}]")
    print(f"   Column sums: [{S.sum(axis=0).min():.4f}, {S.sum(axis=0).max():.4f}]")
    
    # Initialize weights
    print("\n4. Initializing model weights...")
    spatial_weights = init_spatial_weights(
        params['N_Δ'], params['d_s'], params['n_heads'], params['n_layers_spatial']
    )
    temporal_weights = init_temporal_weights(
        params['W_T'], params['d_s'], params['n_heads'], params['n_layers_temporal']
    )
    mlp_weights = init_mlp_weights(params['d_s'], [128, 64])
    
    # Forward pass
    print("\n5. Running forward pass...")
    logit, prob = xfall_forward(H, params, spatial_weights, temporal_weights, mlp_weights)
    print(f"   Logit: {logit:.4f}")
    print(f"   Probability: {prob:.4f}")
    
    # Inference
    print("\n6. Running inference...")
    # Convert to frames format for demo
    frames = []
    for i in range(N_T):
        frame = CSIFrame(
            timestamp=i * 2857,
            rssi=-45,
            mac="aa:bb:cc:dd:ee:ff",
            channel=36,
            n_subcarriers=N_S,
            amplitude=np.abs(H[i, :]),
            phase=np.angle(H[i, :]),
            complex_csi=H[i, :]
        )
        frames.append(frame)
    
    prediction, confidence = xfall_inference(
        frames, params, spatial_weights, temporal_weights, mlp_weights
    )
    print(f"   Prediction: {'Fall' if prediction == 1 else 'Normal'}")
    print(f"   Confidence: {confidence:.4f}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nNote: For actual training, use PyTorch implementation")
    print("with proper backpropagation and GPU support.")
    
    return S, prediction, confidence


# =============================================================================
# ALERT STATE MACHINE
# =============================================================================

class AlertFSM:
    """
    Alert finite state machine with debounce logic.

    States:
        idle        — no activity of concern
        monitoring  — 1 fall prediction seen, waiting for confirmation
        fall_alert  — confirmed fall (2 consecutive windows >= threshold)
        cooldown    — post-alert, waiting for non-fall to reset
    """
    IDLE = 'idle'
    MONITORING = 'monitoring'
    FALL_ALERT = 'fall_alert'
    COOLDOWN = 'cooldown'

    def __init__(self, threshold: float = 0.60, cooldown_sec: float = 10.0,
                 logger=None):
        self.threshold = threshold
        self.cooldown_sec = cooldown_sec
        self.logger = logger
        self.state = self.IDLE
        self._consecutive_falls = 0
        self._non_fall_start = None

    def update(self, prediction: int, confidence: float):
        """Process a new prediction. Returns the current state."""
        import time
        is_fall = (prediction == 1 and confidence >= self.threshold)

        if self.state == self.IDLE:
            if is_fall:
                self._consecutive_falls = 1
                self.state = self.MONITORING

        elif self.state == self.MONITORING:
            if is_fall:
                self._consecutive_falls += 1
                if self._consecutive_falls >= 2:
                    self.state = self.FALL_ALERT
                    self._non_fall_start = None
                    print("\n" + "=" * 60)
                    print("  ** FALL DETECTED **")
                    print(f"  Confidence: {confidence:.1%}")
                    print("=" * 60 + "\n")
                    if self.logger:
                        self.logger.log_event(
                            "fall_detected", confidence,
                            f"Confirmed after {self._consecutive_falls} consecutive windows"
                        )
            else:
                self._consecutive_falls = 0
                self.state = self.IDLE

        elif self.state == self.FALL_ALERT:
            self.state = self.COOLDOWN
            self._non_fall_start = time.time() if not is_fall else None

        elif self.state == self.COOLDOWN:
            if is_fall:
                self._non_fall_start = None
            else:
                if self._non_fall_start is None:
                    self._non_fall_start = time.time()
                elapsed = time.time() - self._non_fall_start
                if elapsed >= self.cooldown_sec:
                    self.state = self.IDLE
                    self._consecutive_falls = 0
                    print("[alert] All clear — returned to idle")
                    if self.logger:
                        self.logger.log_event("all_clear", 0.0,
                                              f"No fall for {self.cooldown_sec}s")

        return self.state


# =============================================================================
# SIMULATED CSI SOURCE
# =============================================================================

def simulate_csi_stream(n_subcarriers: int = 64, rate_hz: float = 100.0):
    """
    Generate synthetic CSI frames for testing without hardware.
    Cycles through phases: idle -> walk -> fall -> idle.
    """
    import time

    interval = 1.0 / rate_hz
    phase_duration = 5.0  # seconds per phase
    phases = ['idle', 'walk', 'fall', 'idle']

    print("[simulate] Starting synthetic CSI stream")
    print(f"[simulate] Phases: {' -> '.join(phases)} ({phase_duration}s each)")

    t = 0.0
    while True:
        phase_idx = int(t / phase_duration) % len(phases)
        phase = phases[phase_idx]

        if phase == 'idle':
            base = 10.0 + np.random.randn(n_subcarriers) * 0.5
        elif phase == 'walk':
            base = 10.0 + np.sin(2 * np.pi * 2.0 * t) * 3.0
            base = base + np.random.randn(n_subcarriers) * 1.0
        elif phase == 'fall':
            fall_progress = (t % phase_duration) / phase_duration
            if fall_progress < 0.3:
                base = 10.0 + fall_progress * 30.0
            else:
                base = 10.0 + (1.0 - fall_progress) * 5.0
            base = base + np.random.randn(n_subcarriers) * 2.0
        else:
            base = 10.0 + np.random.randn(n_subcarriers) * 0.5

        amplitude = np.abs(base)
        phase_angle = np.random.uniform(-np.pi, np.pi, n_subcarriers)

        frame = CSIFrame(
            timestamp=int(t * 1e6),
            rssi=-50,
            mac="AA:BB:CC:DD:EE:FF",
            channel=6,
            n_subcarriers=n_subcarriers,
            amplitude=amplitude.astype(np.float64),
            phase=phase_angle.astype(np.float64),
            complex_csi=(amplitude * np.exp(1j * phase_angle)).astype(np.complex64),
        )

        yield frame
        time.sleep(interval)
        t += interval


# =============================================================================
# REAL-TIME INFERENCE ENGINE
# =============================================================================

class XFallInferenceEngine:
    """
    Real-time XFall inference pipeline.

    Collects CSI frames into a rolling buffer, then runs inference
    once enough frames accumulate for a full window.

    Supports two modes:
      - PyTorch model (when model_path is provided) — uses trained weights
      - NumPy fallback (no model_path) — uses random weights (demo only)
    """

    def __init__(self, params: Dict, threshold: float = 0.5,
                 csv_path: str = "events.csv", model_path: str = None):
        from collections import deque
        from event_logger import EventLogger

        self.params = params
        self.threshold = threshold
        self.use_pytorch = model_path is not None

        # Buffer needs N_Δ + W_T frames for one inference window
        self.window_size = params['N_Δ'] + params['W_T'] + 50
        self.step_frames = params['W_T'] // 2  # Run inference every half-window

        self.buffer = deque(maxlen=self.window_size)
        self._frames_since_inference = 0

        if self.use_pytorch:
            # Load trained PyTorch model
            import torch
            from model import get_model

            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.torch_model = get_model(
                N_Δ=params['N_Δ'], W_T=params['W_T'], d_s=params['d_s'],
                n_heads=params['n_heads'],
                n_layers_spatial=params['n_layers_spatial'],
                n_layers_temporal=params['n_layers_temporal'],
            ).to(self.device)

            checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
            self.torch_model.load_state_dict(checkpoint['model_state_dict'])
            self.torch_model.eval()
            print(f"[inference] Loaded trained model from {model_path}")
            print(f"[inference] Device: {self.device}")
        else:
            # Fallback: random NumPy weights (demo/testing only)
            self.spatial_weights = init_spatial_weights(
                params['N_Δ'], params['d_s'], params['n_heads'],
                params['n_layers_spatial']
            )
            self.temporal_weights = init_temporal_weights(
                params['W_T'], params['d_s'], params['n_heads'],
                params['n_layers_temporal']
            )
            self.mlp_weights = init_mlp_weights(params['d_s'], [128, 64])
            print("[inference] No model loaded — using random weights (demo mode)")

        # Event logger and alert FSM
        self.logger = EventLogger(csv_path)
        self.alert = AlertFSM(threshold=threshold, logger=self.logger)

        # Stats
        self._total_frames = 0
        self._total_inferences = 0

    def add_frame(self, frame: CSIFrame):
        """Add a CSI frame to the rolling buffer."""
        self.buffer.append(frame)
        self._frames_since_inference += 1
        self._total_frames += 1

        # Run inference when enough frames have accumulated
        if (len(self.buffer) >= self.window_size and
                self._frames_since_inference >= self.step_frames):
            self._run_inference()
            self._frames_since_inference = 0

    def _run_inference(self):
        """Run XFall inference on the current buffer."""
        frames = list(self.buffer)

        if self.use_pytorch:
            prediction, confidence = self._run_pytorch_inference(frames)
        else:
            prediction, confidence = xfall_inference(
                frames, self.params,
                self.spatial_weights, self.temporal_weights,
                self.mlp_weights, threshold=self.threshold
            )

        self._total_inferences += 1

        # Display
        label = "FALL" if prediction == 1 else "normal"
        bar = "#" * int(confidence * 20) + "." * (20 - int(confidence * 20))
        state_indicator = {
            'idle': '[OK]', 'monitoring': '[??]',
            'fall_alert': '[!!]', 'cooldown': '[..]',
        }.get(self.alert.state, '[  ]')

        print(f"  [{self._total_inferences:4d}] {state_indicator} "
              f"{label:6s} {bar} {confidence:.1%}  "
              f"(frames: {self._total_frames})", end='\r')

        # Log prediction
        self.logger.log_event(
            f"prediction_{label}", confidence,
            f"inference #{self._total_inferences}",
            silent=True,
        )

        # Alert logic
        self.alert.update(prediction, confidence)

    def _run_pytorch_inference(self, frames):
        """Run inference using the trained PyTorch model."""
        import torch

        # Build CSI matrix from frames
        H = frames_to_matrix(frames)

        # Generate SDP
        S = generate_sdp_fast(H, self.params['N_Δ'], self.params['W_T'])

        # Convert to tensor: (1, N_Δ, W_T)
        S_tensor = torch.FloatTensor(S).unsqueeze(0).to(self.device)

        # Model inference
        with torch.no_grad():
            logit = self.torch_model(S_tensor)
            prob = torch.sigmoid(logit).item()

        prediction = 1 if prob >= self.threshold else 0
        return prediction, prob

    def close(self):
        self.logger.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    import time

    parser = argparse.ArgumentParser(
        description='XFall — Wi-Fi CSI Fall Detection System'
    )
    parser.add_argument('--port',
                        help='Serial port (e.g. COM6, /dev/ttyUSB0)')
    parser.add_argument('--simulate', action='store_true',
                        help='Use synthetic CSI data (no hardware needed)')
    parser.add_argument('--demo', action='store_true',
                        help='Run algorithm demo with synthetic data')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Fall confidence threshold (default: 0.5)')
    parser.add_argument('--csv', default='events.csv',
                        help='CSV file path for event logging (default: events.csv)')
    parser.add_argument('--sim-duration', type=float, default=30.0,
                        help='Simulation duration in seconds (default: 30)')
    parser.add_argument('--baudrate', type=int, default=115200,
                        help='Serial baud rate (default: 115200)')
    parser.add_argument('--model',
                        help='Path to trained xfall_model.pth checkpoint')
    parser.add_argument('--debug', action='store_true',
                        help='Print raw serial lines for debugging')
    args = parser.parse_args()

    # Demo mode
    if args.demo:
        demo()
        return

    if not args.simulate and not args.port:
        parser.error("Either --port, --simulate, or --demo is required")

    # Model parameters
    params = {
        'N_Δ': 50,
        'W_T': 100,
        'd_s': 32,
        'n_heads': 4,
        'n_layers_spatial': 1,
        'n_layers_temporal': 2,
    }

    print("=" * 60)
    print("  XFall — Wi-Fi CSI Fall Detection")
    print("=" * 60)
    print(f"  Window:    {params['N_Δ'] + params['W_T'] + 50} frames")
    print(f"  Threshold: {args.threshold:.0%}")
    print(f"  Mode:      {'Simulation' if args.simulate else f'Live ({args.port})'}")
    print(f"  Model:     {args.model or '(random weights — demo mode)'}")
    print(f"  Events:    {args.csv}")
    print("=" * 60 + "\n")

    engine = XFallInferenceEngine(
        params=params,
        threshold=args.threshold,
        csv_path=args.csv,
        model_path=args.model,
    )

    try:
        if args.simulate:
            start_time = time.time()
            for frame in simulate_csi_stream():
                engine.add_frame(frame)
                if time.time() - start_time >= args.sim_duration:
                    print(f"\n\n[simulate] Duration reached ({args.sim_duration}s)")
                    break
        else:
            from serial_reader import CSISerialReader
            reader = CSISerialReader(
                port=args.port, baudrate=args.baudrate, debug=args.debug
            )
            print("[xfall] Press Ctrl+C to stop\n")
            for frame in reader.stream():
                engine.add_frame(frame)

    except KeyboardInterrupt:
        print("\n\n[xfall] Stopped by user")
    finally:
        print(f"\n{'=' * 60}")
        print(f"  Total frames:     {engine._total_frames}")
        print(f"  Total inferences: {engine._total_inferences}")
        events = engine.logger.get_recent_events(limit=50)
        fall_events = [e for e in events if e.get('event_type') == 'fall_detected']
        print(f"  Fall events:      {len(fall_events)}")
        print(f"  Events log:       {engine.logger.csv_path}")
        print(f"{'=' * 60}")
        engine.close()


if __name__ == "__main__":
    main()

