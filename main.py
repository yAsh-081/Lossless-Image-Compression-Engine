import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import struct
import heapq
import pickle
import time
import os
import threading
from collections import defaultdict, Counter

class BMPParser:
    def __init__(self):
        self.file_size = 0
        self.width = 0
        self.height = 0
        self.bits_per_pixel = 0
        self.color_table = []
        self.pixel_data = None
        self.raw_image_data = None
        
    def parse_bmp(self, file_path):
        # Parse BMP file and extract metadata and pixel data
        # This method reads the BMP file, extracts metadata, and prepares pixel data, The data extracted includes: File size, width, height, bits per pixel, color table (if applicable), and raw pixel data.
        try:    # use try-except to handle file reading errors, this will ensure that if the file is not a valid BMP or cannot be read, an error message is shown to the user. And the code will not crash.
            with open(file_path, "rb") as f:
                bmp_bytes = f.read()
            
            # Check if it's a valid BMP file (starts with 'BM'), this was gavien in the assignment description and resource given by the instructor.
            if bmp_bytes[0:2] != b'BM':
                raise ValueError("Not a valid BMP file")
            
            # Parse header metadata, this does not parse the BMP file, this only help interpret the binary data.
            self.file_size = struct.unpack('<I', bmp_bytes[2:6])[0]
            
            # DIB header: size at 14, width at 18, height at 22, bpp at 28, pixel data offset at 10.
            # All values are little-endian; color table follows DIB header for <=8bpp.
            dib_header_size = struct.unpack('<I', bmp_bytes[14:18])[0]
            self.width = struct.unpack('<I', bmp_bytes[18:22])[0]
            self.height = struct.unpack('<I', bmp_bytes[22:26])[0]
            self.bits_per_pixel = struct.unpack('<H', bmp_bytes[28:30])[0]
            
            # Get pixel data offset, which is the position in the file where the pixel data starts.
            # This is stored at offset 10 in the BMP header.
            pixel_data_offset = struct.unpack('<I', bmp_bytes[10:14])[0]
            
            # Parse color table if needed (for 1, 4, 8 bit images)
            if self.bits_per_pixel <= 8:
                self._parse_color_table(bmp_bytes, 14 + dib_header_size)
            
            # Parse pixel data, which starts at the pixel data offset.
            # The pixel data is stored in BGR format for 24-bit images, and in indexed color format for 1, 4, and 8-bit images.
            # For 24-bit images, each pixel is represented by 3 bytes (BGR).
            # For 8-bit images, each pixel is represented by 1 byte, which is an index into the color table.
            # For 4-bit images, each pixel is represented by 1 nibble (4 bits), and two pixels are packed into one byte.
            # For 1-bit images, each pixel is represented by 1 bit, and 8 pixels are packed into one byte.
            # The pixel data is stored in rows, with each row padded to a multiple of 4 bytes.
            self.raw_image_data = bmp_bytes[pixel_data_offset:]
            self.pixel_data = self._parse_pixel_data()
            
            return True
            
        except Exception as e:  # handle any exceptions that occur during file reading or parsing
            messagebox.showerror("Error", f"Failed to parse BMP file: {str(e)}")
            return False
    
    def _parse_color_table(self, bmp_bytes, offset):
        # Parse the color table for indexed color BMPs (1, 4, 8 bits per pixel)
        num_colors = 2 ** self.bits_per_pixel
        self.color_table = []   # This will store the color table entries as tuples of (R, G, B).
        
        # Each color entry is 4 bytes (BGRA), so we read num_colors * 4 bytes from the offset.
        # The color table is used for indexed color BMPs, where each pixel value is an index into this table.
        for i in range(num_colors):
            # Each color entry is 4 bytes (BGRA)
            color_offset = offset + i * 4
            if color_offset + 3 < len(bmp_bytes):
                b = bmp_bytes[color_offset]
                g = bmp_bytes[color_offset + 1]
                r = bmp_bytes[color_offset + 2]
                self.color_table.append((r, g, b))
    
    def _parse_pixel_data(self):
        # Parse the pixel data based on bits per pixel
        # This method converts the raw pixel data into a numpy array of RGB values.
        # The pixel data is stored in BGR format for 24-bit images, and in indexed color format for 1, 4, and 8-bit images.
        # The pixel data is stored in rows, with each row padded to a multiple of 4 bytes.
        # The pixel data is read from the raw_image_data attribute, which contains the bytes after the pixel data offset.
        # Calculate row padding (rows must be multiple of 4 bytes)
        row_size = ((self.bits_per_pixel * self.width + 31) // 32) * 4
        
        # Initialize image array, which will hold the pixel data as a numpy array.
        # The image array will have shape (height, width, 3) for RGB images.
        # For indexed color images, it will have shape (height, width, 3) but the colors will be looked up from the color table.
        # The dtype is set to uint8 to hold RGB values in the range 0-255.
        image = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        if self.bits_per_pixel == 24:
            # 24-bit RGB
            for y in range(self.height):
                # BMP stores rows bottom to top
                row_start = y * row_size
                actual_y = self.height - 1 - y
                
                for x in range(self.width):
                    pixel_start = row_start + x * 3
                    if pixel_start + 2 < len(self.raw_image_data):
                        # BMP stores as BGR
                        b = self.raw_image_data[pixel_start]
                        g = self.raw_image_data[pixel_start + 1]
                        r = self.raw_image_data[pixel_start + 2]
                        image[actual_y, x] = [r, g, b]
        
        elif self.bits_per_pixel == 8:
            # 8-bit indexed color
            for y in range(self.height):
                row_start = y * row_size
                actual_y = self.height - 1 - y
                
                for x in range(self.width):
                    pixel_start = row_start + x
                    if pixel_start < len(self.raw_image_data):
                        color_index = self.raw_image_data[pixel_start]
                        if color_index < len(self.color_table):
                            image[actual_y, x] = self.color_table[color_index]
        
        elif self.bits_per_pixel == 4:
            # 4-bit indexed color
            for y in range(self.height):
                row_start = y * row_size
                actual_y = self.height - 1 - y
                
                for x in range(self.width):
                    byte_index = row_start + x // 2
                    if byte_index < len(self.raw_image_data):
                        byte_val = self.raw_image_data[byte_index]
                        if x % 2 == 0:
                            color_index = (byte_val >> 4) & 0x0F
                        else:
                            color_index = byte_val & 0x0F
                        
                        if color_index < len(self.color_table):
                            image[actual_y, x] = self.color_table[color_index]
        
        elif self.bits_per_pixel == 1:
            # 1-bit indexed color
            for y in range(self.height):
                row_start = y * row_size
                actual_y = self.height - 1 - y
                
                for x in range(self.width):
                    byte_index = row_start + x // 8
                    if byte_index < len(self.raw_image_data):
                        byte_val = self.raw_image_data[byte_index]
                        bit_position = 7 - (x % 8)
                        color_index = (byte_val >> bit_position) & 1
                        
                        if color_index < len(self.color_table):
                            image[actual_y, x] = self.color_table[color_index]
        
        return image

# Add this new class after the BMPParser class
class HuffmanNode:
    def __init__(self, char, freq, left=None, right=None):
        self.char = char
        self.freq = freq
        self.left = left
        self.right = right
    
    def __lt__(self, other):
        return self.freq < other.freq

class CompressionEngine:
    def __init__(self, block_size=4096):  # Much larger blocks to reduce overhead
        self.huffman_codes = {}
        self.huffman_tree = None
        self.block_size = block_size
    
    def paeth_predictor(self, a, b, c):
        """Paeth predictor function with proper data type handling"""
        # Convert to int32 to prevent overflow
        a, b, c = int(a), int(b), int(c)
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b) 
        pc = abs(p - c)
        
        if pa <= pb and pa <= pc:
            return a
        elif pb <= pc:
            return b
        else:
            return c
    
    def apply_paeth_encoding(self, data, width, height, channels):
        """Apply Paeth prediction to image data with proper signed arithmetic"""
        predicted_data = np.zeros_like(data, dtype=np.uint8)
        
        for c in range(channels):
            channel_data = data[:, :, c]
            predicted_channel = predicted_data[:, :, c]
            
            for y in range(height):
                for x in range(width):
                    if x == 0 and y == 0:
                        # First pixel - no prediction
                        predicted_channel[y, x] = channel_data[y, x]
                    elif x == 0:
                        # First column - predict from above
                        diff = int(channel_data[y, x]) - int(channel_data[y-1, x])
                        predicted_channel[y, x] = (diff + 256) % 256  # Proper modular arithmetic
                    elif y == 0:
                        # First row - predict from left
                        diff = int(channel_data[y, x]) - int(channel_data[y, x-1])
                        predicted_channel[y, x] = (diff + 256) % 256  # Proper modular arithmetic
                    else:
                        # Use Paeth predictor
                        a = int(channel_data[y, x-1])     # left
                        b = int(channel_data[y-1, x])     # above
                        c = int(channel_data[y-1, x-1])   # upper-left
                        
                        predictor = self.paeth_predictor(a, b, c)
                        diff = int(channel_data[y, x]) - predictor
                        predicted_channel[y, x] = (diff + 256) % 256  # Proper modular arithmetic
        
        return predicted_data
    
    def reverse_paeth_encoding(self, predicted_data, width, height, channels):
        """Reverse Paeth prediction to recover original data with proper signed arithmetic"""
        original_data = np.zeros_like(predicted_data, dtype=np.uint8)
        
        for c in range(channels):
            predicted_channel = predicted_data[:, :, c]
            original_channel = original_data[:, :, c]
            
            for y in range(height):
                for x in range(width):
                    if x == 0 and y == 0:
                        # First pixel - no prediction was applied
                        original_channel[y, x] = predicted_channel[y, x]
                    elif x == 0:
                        # First column - predicted from above
                        diff = int(predicted_channel[y, x])
                        if diff > 127:  # Convert from unsigned to signed
                            diff -= 256
                        restored = (int(original_channel[y-1, x]) + diff) % 256
                        original_channel[y, x] = restored
                    elif y == 0:
                        # First row - predicted from left
                        diff = int(predicted_channel[y, x])
                        if diff > 127:  # Convert from unsigned to signed
                            diff -= 256
                        restored = (int(original_channel[y, x-1]) + diff) % 256
                        original_channel[y, x] = restored
                    else:
                        # Use Paeth predictor
                        a = int(original_channel[y, x-1])     # left
                        b = int(original_channel[y-1, x])     # above
                        c = int(original_channel[y-1, x-1])   # upper-left
                        
                        predictor = self.paeth_predictor(a, b, c)
                        diff = int(predicted_channel[y, x])
                        if diff > 127:  # Convert from unsigned to signed
                            diff -= 256
                        restored = (predictor + diff) % 256
                        original_channel[y, x] = restored
        
        return original_data
    
    def run_length_encode(self, data):
        """Apply Run-Length Encoding with compression check"""
        if len(data) == 0:
            return b'', False  # Return empty data and compression flag
        
        encoded = []
        current_byte = data[0]
        count = 1
        
        for i in range(1, len(data)):
            if data[i] == current_byte and count < 255:
                count += 1
            else:
                encoded.extend([count, current_byte])
                current_byte = data[i]
                count = 1
        
        # Don't forget the last run
        encoded.extend([count, current_byte])
        
        encoded_bytes = bytes(encoded)
        
        # Check if RLE actually compressed the data
        if len(encoded_bytes) >= len(data):
            return data, False  # Return original data if RLE doesn't help
        
        return encoded_bytes, True
    
    def run_length_decode(self, encoded_data):
        """Decode Run-Length Encoded data"""
        if len(encoded_data) == 0:
            return b''
        
        decoded = []
        for i in range(0, len(encoded_data), 2):
            if i + 1 < len(encoded_data):
                count = encoded_data[i]
                value = encoded_data[i + 1]
                decoded.extend([value] * count)
        
        return bytes(decoded)
    
    def build_huffman_tree(self, data):
        """Build Huffman tree from data"""
        if not data:
            return None
        
        # Count frequencies
        freq_map = Counter(data)
        
        # Handle single character case
        if len(freq_map) == 1:
            char = list(freq_map.keys())[0]
            return HuffmanNode(char, freq_map[char])
        
        # Create priority queue
        heap = []
        for char, freq in freq_map.items():
            heapq.heappush(heap, HuffmanNode(char, freq))
        
        # Build tree
        while len(heap) > 1:
            left = heapq.heappop(heap)
            right = heapq.heappop(heap)
            merged = HuffmanNode(None, left.freq + right.freq, left, right)
            heapq.heappush(heap, merged)
        
        return heap[0]
    
    def build_codes(self, root):
        """Build Huffman codes from tree"""
        if not root:
            return {}
        
        # Handle single character case
        if root.char is not None:
            return {root.char: '0'}
        
        codes = {}
        
        def traverse(node, code):
            if node.char is not None:
                codes[node.char] = code
            else:
                if node.left:
                    traverse(node.left, code + '0')
                if node.right:
                    traverse(node.right, code + '1')
        
        traverse(root, '')
        return codes
    
    def huffman_encode(self, data):
        """Encode data using Huffman coding"""
        if not data:
            return b'', None, 0
        
        # Build tree and codes
        huffman_tree = self.build_huffman_tree(data)
        huffman_codes = self.build_codes(huffman_tree)
        
        # Encode data
        encoded_bits = ''.join(huffman_codes[byte] for byte in data)
        
        # Convert bits to bytes
        encoded_bytes = bytearray()
        for i in range(0, len(encoded_bits), 8):
            byte_bits = encoded_bits[i:i+8]
            if len(byte_bits) < 8:
                byte_bits = byte_bits.ljust(8, '0')  # Pad with zeros
            encoded_bytes.append(int(byte_bits, 2))
        
        return bytes(encoded_bytes), huffman_tree, len(encoded_bits)
    
    def serialize_huffman_tree(self, tree):
        """Efficiently serialize Huffman tree to bytes"""
        if not tree:
            return b''
        
        def serialize_node(node):
            if node.char is not None:
                # Leaf node: 1 byte flag + 1 byte character
                return b'\x01' + bytes([node.char])
            else:
                # Internal node: 1 byte flag + left subtree + right subtree
                left_data = serialize_node(node.left) if node.left else b''
                right_data = serialize_node(node.right) if node.right else b''
                return b'\x00' + left_data + right_data
        
        return serialize_node(tree)
    
    def deserialize_huffman_tree(self, data):
        """Deserialize Huffman tree from bytes"""
        if not data:
            return None, 0
        
        def deserialize_node(data, pos):
            if pos >= len(data):
                return None, pos
            
            if data[pos] == 1:  # Leaf node
                if pos + 1 < len(data):
                    char = data[pos + 1]
                    return HuffmanNode(char, 0), pos + 2
                return None, pos + 1
            else:  # Internal node
                left_node, pos = deserialize_node(data, pos + 1)
                right_node, pos = deserialize_node(data, pos)
                return HuffmanNode(None, 0, left_node, right_node), pos
        
        tree, _ = deserialize_node(data, 0)
        return tree
    
    def huffman_decode(self, encoded_data, bit_length, huffman_tree):
        """Decode Huffman encoded data"""
        if not encoded_data or not huffman_tree:
            return b''
        
        # Handle single character case
        if huffman_tree.char is not None:
            # For single character, each bit represents one occurrence
            # But we need to calculate how many characters based on bit_length and code length
            # Since single char gets code '0', each character is 1 bit
            return bytes([huffman_tree.char] * bit_length)
        
        # Convert bytes back to bits
        bit_string = ''.join(format(byte, '08b') for byte in encoded_data)
        bit_string = bit_string[:bit_length]  # Trim to actual length
        
        # Decode using tree
        decoded_data = []
        current_node = huffman_tree
        
        for bit in bit_string:
            if bit == '0':
                current_node = current_node.left
            else:
                current_node = current_node.right
            
            if current_node and current_node.char is not None:
                decoded_data.append(current_node.char)
                current_node = huffman_tree
        
        return bytes(decoded_data)
    
    def compress_block(self, block_data):
        """Compress a single block with fallback to raw storage"""
        original_size = len(block_data)
        
        # Apply RLE first
        rle_data, rle_compressed = self.run_length_encode(block_data)
        
        # Apply Huffman encoding
        huffman_data, huffman_tree, bit_length = self.huffman_encode(rle_data)
        
        # Check if compression is beneficial (using efficient tree storage)
        tree_data = self.serialize_huffman_tree(huffman_tree) if huffman_tree else b''
        compressed_size = len(huffman_data) + len(tree_data) + 8  # +8 for bit_length storage
        
        # More aggressive compression threshold - even small savings are worthwhile
        compression_threshold = 0.95 if original_size < 1024 else 0.90
        
        if compressed_size >= original_size * compression_threshold:
            # Store raw data
            return {
                'type': 'raw',
                'data': block_data,
                'original_size': original_size
            }
        else:
            # Store compressed data
            return {
                'type': 'compressed',
                'data': huffman_data,
                'tree_data': tree_data,
                'bit_length': bit_length,
                'rle_used': rle_compressed,
                'original_size': original_size
            }
    
    def decompress_block(self, block_info):
        """Decompress a single block"""
        if block_info['type'] == 'raw':
            return block_info['data']
        else:
            # Deserialize Huffman tree
            huffman_tree = self.deserialize_huffman_tree(block_info['tree_data'])
            
            # Decompress Huffman data
            rle_data = self.huffman_decode(
                block_info['data'], 
                block_info['bit_length'], 
                huffman_tree
            )
            
            # Decode RLE if it was used
            if block_info.get('rle_used', True):  # Default to True for backward compatibility
                original_data = self.run_length_decode(rle_data)
            else:
                original_data = rle_data
            
            return original_data
    
    def compress_data(self, pixel_data):
        """Main compression function with adaptive processing based on image characteristics"""
        height, width, channels = pixel_data.shape
        total_pixels = height * width * channels
        
        # Check if this is an indexed color image that was expanded to RGB
        # by examining the entropy and color distribution
        unique_colors = len(np.unique(pixel_data.reshape(-1, 3), axis=0))
        is_likely_indexed = unique_colors <= 256 and total_pixels > unique_colors * 50
        
        if is_likely_indexed:
            # For likely indexed color images, use a different approach
            return self._compress_indexed_like_data(pixel_data)
        
        # For very small RGB images, don't use compression at all  
        if total_pixels < 20000:  # Reduced threshold
            return {
                'type': 'uncompressed',
                'data': pixel_data.astype(np.uint8).tobytes(),
                'original_shape': pixel_data.shape,
                'block_size': self.block_size
            }
        
        # Apply Paeth prediction
        paeth_encoded = self.apply_paeth_encoding(pixel_data, width, height, channels)
        
        # Flatten the data for block processing
        flat_data = paeth_encoded.flatten()
        
        # Use adaptive block size based on image characteristics
        if total_pixels < 100000:  # Small images
            adaptive_block_size = min(2048, self.block_size)
        else:  # Large images
            adaptive_block_size = self.block_size
        
        # Divide into blocks
        block_data = []
        total_blocks = (len(flat_data) + adaptive_block_size - 1) // adaptive_block_size
        
        for i in range(0, len(flat_data), adaptive_block_size):
            block = flat_data[i:i + adaptive_block_size]
            compressed_block = self.compress_block(bytes(block))
            block_data.append(compressed_block)
        
        return {
            'type': 'block_compressed',
            'blocks': block_data,
            'original_shape': pixel_data.shape,
            'block_size': adaptive_block_size
        }
    
    def _compress_indexed_like_data(self, pixel_data):
        """Special compression for data that looks like expanded indexed color"""
        height, width, channels = pixel_data.shape
        
        # Create a color palette from unique colors
        flat_pixels = pixel_data.reshape(-1, 3)
        unique_colors, inverse_indices = np.unique(flat_pixels, axis=0, return_inverse=True)
        
        # If we have few enough colors, estimate if palette compression will be beneficial
        if len(unique_colors) <= 256:
            # Estimate palette compression size
            palette_size = len(unique_colors) * 3
            
            if len(unique_colors) <= 2:
                # 1-bit per pixel
                indices_packed = self._pack_indices_1bit(inverse_indices, len(flat_pixels))
            elif len(unique_colors) <= 16:
                # 4-bit per pixel  
                indices_packed = self._pack_indices_4bit(inverse_indices)
            else:
                # 8-bit per pixel
                indices_packed = inverse_indices.astype(np.uint8).tobytes()
            
            # Test compression of indices
            rle_data, rle_used = self.run_length_encode(indices_packed)
            huffman_data, huffman_tree, bit_length = self.huffman_encode(rle_data)
            tree_data = self.serialize_huffman_tree(huffman_tree) if huffman_tree else b''
            
            # Estimate total palette compression size
            palette_compressed_size = palette_size + len(huffman_data) + len(tree_data) + 50  # overhead
            
            # Estimate the size of regular block compression for comparison
            paeth_encoded = self.apply_paeth_encoding(pixel_data, width, height, channels)
            flat_data = paeth_encoded.flatten()
            
            # Quick estimate of block compression by testing one block
            test_block_size = min(2048, len(flat_data))
            test_block = flat_data[:test_block_size]
            test_compressed = self.compress_block(bytes(test_block))
            
            # Estimate total block compression size based on test block ratio
            test_ratio = len(test_compressed['data']) / len(test_block)
            estimated_block_size = int(len(flat_data) * test_ratio) + (len(flat_data) // test_block_size) * 100  # overhead per block
            
            # Use palette compression only if it's significantly better than block compression
            # and has a reasonable compression ratio
            palette_ratio = len(flat_pixels) * 3 / palette_compressed_size  # vs raw RGB
            block_ratio = len(flat_pixels) * 3 / estimated_block_size      # vs raw RGB
            
            # For high color count (>128), palette must be much better than block compression
            # For medium color count (16-128), palette must be somewhat better
            # For low color count (<16), prefer palette if it's reasonable
            if len(unique_colors) > 128:
                use_palette = palette_compressed_size < estimated_block_size * 0.8 and palette_ratio > 1.1
            elif len(unique_colors) > 16:
                use_palette = palette_compressed_size < estimated_block_size * 0.9 and palette_ratio > 1.05
            else:
                use_palette = palette_ratio > 1.0
            
            if use_palette:
                return {
                    'type': 'palette_compressed',
                    'palette': unique_colors.astype(np.uint8).tobytes(),
                    'compressed_indices': huffman_data,
                    'tree_data': tree_data,
                    'bit_length': bit_length,
                    'rle_used': rle_used,
                    'num_colors': len(unique_colors),
                    'original_shape': pixel_data.shape,
                    'block_size': self.block_size
                }
        
        # Fall back to regular compression if palette isn't beneficial
        return self._compress_regular_rgb(pixel_data)
    
    def _pack_indices_1bit(self, indices, total_pixels):
        """Pack indices into 1 bit per pixel"""
        packed = bytearray()
        for i in range(0, total_pixels, 8):
            byte_val = 0
            for j in range(8):
                if i + j < total_pixels:
                    byte_val |= (indices[i + j] & 1) << (7 - j)
            packed.append(byte_val)
        return bytes(packed)
    
    def _pack_indices_4bit(self, indices):
        """Pack indices into 4 bits per pixel"""
        packed = bytearray()
        for i in range(0, len(indices), 2):
            byte_val = (indices[i] & 0xF) << 4
            if i + 1 < len(indices):
                byte_val |= indices[i + 1] & 0xF
            packed.append(byte_val)
        return bytes(packed)
    
    def _compress_regular_rgb(self, pixel_data):
        """Regular RGB compression with Paeth prediction"""
        height, width, channels = pixel_data.shape
        
        # Apply Paeth prediction
        paeth_encoded = self.apply_paeth_encoding(pixel_data, width, height, channels)
        
        # Flatten and compress in blocks
        flat_data = paeth_encoded.flatten()
        adaptive_block_size = min(4096, max(1024, len(flat_data) // 100))
        
        block_data = []
        for i in range(0, len(flat_data), adaptive_block_size):
            block = flat_data[i:i + adaptive_block_size]
            compressed_block = self.compress_block(bytes(block))
            block_data.append(compressed_block)
        
        return {
            'type': 'block_compressed',
            'blocks': block_data,
            'original_shape': pixel_data.shape,
            'block_size': adaptive_block_size
        }
    
    def decompress_data(self, compressed_info, original_shape):
        """Main decompression function with support for different compression types"""
        
        # Handle uncompressed data
        if compressed_info.get('type') == 'uncompressed':
            flat_data = np.frombuffer(compressed_info['data'], dtype=np.uint8)
            return flat_data.reshape(original_shape)
        
        # Handle palette compressed data
        if compressed_info.get('type') == 'palette_compressed':
            return self._decompress_palette_data(compressed_info, original_shape)
        
        # Handle block compressed data
        if compressed_info.get('type') == 'block_compressed':
            blocks = compressed_info['blocks']
        else:
            # Backward compatibility with old format
            blocks = compressed_info.get('blocks', [])
        
        # Decompress all blocks
        decompressed_blocks = bytearray()
        for block_info in blocks:
            decompressed_block = self.decompress_block(block_info)
            decompressed_blocks.extend(decompressed_block)
        
        # Reconstruct flat array
        flat_data = np.frombuffer(decompressed_blocks, dtype=np.uint8)
        
        # Reshape to original dimensions
        height, width, channels = original_shape
        paeth_encoded = flat_data.reshape(original_shape)
        
        # Reverse Paeth encoding
        original_data = self.reverse_paeth_encoding(paeth_encoded, width, height, channels)
        
        return original_data
    
    def _decompress_palette_data(self, compressed_info, original_shape):
        """Decompress palette-based compressed data"""
        height, width, channels = original_shape
        total_pixels = height * width
        
        # Reconstruct palette
        palette_data = compressed_info['palette']
        num_colors = compressed_info['num_colors']
        palette = np.frombuffer(palette_data, dtype=np.uint8).reshape(-1, 3)
        
        # Decompress indices
        huffman_tree = self.deserialize_huffman_tree(compressed_info['tree_data'])
        rle_data = self.huffman_decode(
            compressed_info['compressed_indices'],
            compressed_info['bit_length'],
            huffman_tree
        )
        
        if compressed_info.get('rle_used', True):
            indices_packed = self.run_length_decode(rle_data)
        else:
            indices_packed = rle_data
        
        # Unpack indices based on bit depth
        if num_colors <= 2:
            indices = self._unpack_indices_1bit(indices_packed, total_pixels)
        elif num_colors <= 16:
            indices = self._unpack_indices_4bit(indices_packed, total_pixels)
        else:
            indices = np.frombuffer(indices_packed, dtype=np.uint8)
        
        # Reconstruct image from palette
        flat_image = palette[indices]
        return flat_image.reshape(original_shape)
    
    def _unpack_indices_1bit(self, packed_data, total_pixels):
        """Unpack 1-bit indices"""
        indices = []
        for i, byte_val in enumerate(packed_data):
            for j in range(8):
                if len(indices) < total_pixels:
                    indices.append((byte_val >> (7 - j)) & 1)
        return np.array(indices[:total_pixels], dtype=np.uint8)
    
    def _unpack_indices_4bit(self, packed_data, total_pixels):
        """Unpack 4-bit indices"""
        indices = []
        for byte_val in packed_data:
            if len(indices) < total_pixels:
                indices.append((byte_val >> 4) & 0xF)
            if len(indices) < total_pixels:
                indices.append(byte_val & 0xF)
        return np.array(indices[:total_pixels], dtype=np.uint8)


class BMPViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("BMP Image Compressor")
        self.root.geometry("1100x760")
        self.root.minsize(850, 600)

        # Color palette
        self.BG     = '#F6F7F9'
        self.CARD   = '#FFFFFF'
        self.TEXT   = '#1F2937'
        self.MUTED  = '#6B7280'
        self.BORDER = '#D1D5DB'
        self.ACCENT = '#2563EB'

        self.root.configure(bg=self.BG)

        self.parser         = BMPParser()
        self.original_image = None
        self.current_image  = None
        self.photo_image    = None

        # Channel states
        self.show_red   = tk.BooleanVar(value=True)
        self.show_green = tk.BooleanVar(value=True)
        self.show_blue  = tk.BooleanVar(value=True)

        # Metadata display variables
        self.meta_vars = {
            'File Size': tk.StringVar(value='—'),
            'Width':     tk.StringVar(value='—'),
            'Height':    tk.StringVar(value='—'),
            'Bit Depth': tk.StringVar(value='—'),
        }

        self._configure_styles()
        self.setup_gui()

    # ── Styles ──────────────────────────────────────────────────────────────
    def _configure_styles(self):
        FONT      = ('Segoe UI', 10)
        FONT_BOLD = ('Segoe UI', 10, 'bold')
        FONT_SM   = ('Segoe UI', 9)
        FONT_XL   = ('Segoe UI', 17, 'bold')

        s = ttk.Style()
        s.theme_use('clam')

        BG, CARD, TEXT        = self.BG, self.CARD, self.TEXT
        MUTED, BORDER, ACCENT = self.MUTED, self.BORDER, self.ACCENT

        s.configure('App.TFrame',  background=BG)
        s.configure('Card.TFrame', background=CARD)

        s.configure('TLabel',             background=BG,   foreground=TEXT,  font=FONT)
        s.configure('Card.TLabel',        background=CARD,  foreground=TEXT,  font=FONT)
        s.configure('CardBold.TLabel',    background=CARD,  foreground=TEXT,  font=FONT_BOLD)
        s.configure('Muted.TLabel',       background=CARD,  foreground=MUTED, font=FONT_SM)
        s.configure('Title.TLabel',       background=BG,    foreground=TEXT,  font=FONT_XL)
        s.configure('Subtitle.TLabel',    background=BG,    foreground=MUTED, font=FONT_SM)
        s.configure('SectionHead.TLabel', background=CARD,  foreground=TEXT,  font=FONT_BOLD)

        s.configure('TButton',
                    font=FONT, padding=(10, 5),
                    background='#E5E7EB', foreground=TEXT,
                    relief='flat', borderwidth=0)
        s.map('TButton',
              background=[('active', '#D1D5DB'), ('pressed', '#9CA3AF')],
              relief=[('pressed', 'flat'), ('!pressed', 'flat')])

        s.configure('Accent.TButton',
                    font=FONT_BOLD, padding=(12, 6),
                    background=ACCENT, foreground='white',
                    relief='flat', borderwidth=0)
        s.map('Accent.TButton',
              background=[('active', '#1D4ED8'), ('pressed', '#1E40AF')],
              foreground=[('active', 'white'), ('pressed', 'white')])

        s.configure('TScale',
                    background=CARD, troughcolor='#E5E7EB',
                    sliderlength=18, sliderrelief='flat')
        s.map('TScale', background=[('active', CARD)])

        s.configure('TCheckbutton', background=CARD, foreground=TEXT, font=FONT)
        s.map('TCheckbutton',
              background=[('active', CARD)],
              indicatorcolor=[('selected', ACCENT), ('!selected', '#E5E7EB')])

        s.configure('TScrollbar',
                    background='#E5E7EB', troughcolor=CARD,
                    relief='flat', borderwidth=0, arrowsize=13)
        s.map('TScrollbar', background=[('active', '#9CA3AF')])

    def _card(self, parent, **kwargs):
        """White card frame with a 1 px border."""
        return tk.Frame(parent, bg=self.CARD,
                        highlightbackground=self.BORDER, highlightthickness=1,
                        **kwargs)

    # ── Layout ──────────────────────────────────────────────────────────────
    def setup_gui(self):
        PAD = 16
        GAP = 12

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Outer wrapper
        wrap = tk.Frame(self.root, bg=self.BG)
        wrap.grid(row=0, column=0, sticky='nsew', padx=PAD, pady=PAD)
        wrap.grid_rowconfigure(2, weight=1)
        wrap.grid_columnconfigure(0, weight=0, minsize=268)
        wrap.grid_columnconfigure(1, weight=1)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(wrap, bg=self.BG)
        hdr.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, GAP))
        ttk.Label(hdr, text="BMP Image Compressor",
                  style='Title.TLabel').pack(side='left')
        ttk.Label(hdr,
                  text="  Open, preview, compress, and inspect BMP images.",
                  style='Subtitle.TLabel').pack(side='left', pady=(8, 0))

        # ── Toolbar ─────────────────────────────────────────────────────────
        tb = self._card(wrap)
        tb.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, GAP))
        tb_row = tk.Frame(tb, bg=self.CARD)
        tb_row.pack(fill='x', padx=14, pady=10)

        _btn_open = ttk.Button(tb_row, text="Open BMP",
                               command=self.open_file,
                               style='Accent.TButton')
        _btn_open.pack(side='left', padx=(0, 8))

        _btn_compress = ttk.Button(tb_row, text="Compress",
                                   command=self.compress_image,
                                   style='TButton')
        _btn_compress.pack(side='left', padx=(0, 8))

        _btn_open_c = ttk.Button(tb_row, text="Open Compressed",
                                 command=self.open_custom_compressed_file,
                                 style='TButton')
        _btn_open_c.pack(side='left')

        # Keep refs so we can disable/enable them during long operations
        self._action_buttons = [_btn_open, _btn_compress, _btn_open_c]

        # Inline loading indicator — hidden by default, shown via _start_loading()
        self._loading_frame = tk.Frame(tb_row, bg=self.CARD)
        self._spin_canvas   = tk.Canvas(self._loading_frame, width=18, height=18,
                                        bg=self.CARD, highlightthickness=0)
        self._spin_canvas.pack(side='left', padx=(0, 6))
        self._loading_label = tk.Label(self._loading_frame, text='',
                                       bg=self.CARD, fg=self.MUTED,
                                       font=('Segoe UI', 9))
        self._loading_label.pack(side='left')
        # _loading_frame is intentionally NOT packed yet

        # ── Left panel ──────────────────────────────────────────────────────
        left = tk.Frame(wrap, bg=self.BG)
        left.grid(row=2, column=0, sticky='nsew', padx=(0, GAP))
        left.grid_columnconfigure(0, weight=1)

        # — Metadata card —
        meta_card = self._card(left)
        meta_card.grid(row=0, column=0, sticky='ew', pady=(0, GAP))

        mi = tk.Frame(meta_card, bg=self.CARD)
        mi.pack(fill='x', padx=14, pady=12)
        mi.grid_columnconfigure(1, weight=1)

        ttk.Label(mi, text="Image Info",
                  style='SectionHead.TLabel').grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))

        for idx, (lbl, key) in enumerate([
            ("File Size",  'File Size'),
            ("Width",      'Width'),
            ("Height",     'Height'),
            ("Bit Depth",  'Bit Depth'),
        ], start=1):
            ttk.Label(mi, text=lbl,
                      style='CardBold.TLabel').grid(
                row=idx, column=0, sticky='w', pady=3)
            ttk.Label(mi, textvariable=self.meta_vars[key],
                      style='Muted.TLabel').grid(
                row=idx, column=1, sticky='e', pady=3, padx=(16, 0))

        # Compression result line (shown after compress action)
        self.comp_result_label = ttk.Label(
            meta_card, text='', style='Muted.TLabel',
            wraplength=230, justify='left')
        self.comp_result_label.pack(anchor='w', padx=14, pady=(0, 10))

        # — Controls card —
        ctrl_card = self._card(left)
        ctrl_card.grid(row=1, column=0, sticky='ew')

        ci = tk.Frame(ctrl_card, bg=self.CARD)
        ci.pack(fill='x', padx=14, pady=12)
        ci.grid_columnconfigure(1, weight=1)

        ttk.Label(ci, text="Image Controls",
                  style='SectionHead.TLabel').grid(
            row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        # Brightness
        ttk.Label(ci, text="Brightness",
                  style='CardBold.TLabel').grid(row=1, column=0, sticky='w')
        self.brightness_var   = tk.DoubleVar(value=100)
        self.brightness_label = ttk.Label(ci, text="100%",
                                          style='Muted.TLabel', width=5)
        self.brightness_label.grid(row=1, column=2, sticky='e', padx=(6, 0))
        ttk.Scale(ci, from_=0, to=100,
                  variable=self.brightness_var, orient='horizontal',
                  command=self.update_image).grid(
            row=2, column=0, columnspan=2, sticky='ew', pady=(2, 10))

        # Scale
        ttk.Label(ci, text="Scale",
                  style='CardBold.TLabel').grid(row=3, column=0, sticky='w')
        self.scale_var   = tk.DoubleVar(value=100)
        self.scale_label = ttk.Label(ci, text="100%",
                                     style='Muted.TLabel', width=5)
        self.scale_label.grid(row=3, column=2, sticky='e', padx=(6, 0))
        ttk.Scale(ci, from_=1, to=100,
                  variable=self.scale_var, orient='horizontal',
                  command=self.update_image).grid(
            row=4, column=0, columnspan=2, sticky='ew', pady=(2, 10))

        # RGB channels
        ttk.Label(ci, text="Visible channels",
                  style='CardBold.TLabel').grid(
            row=5, column=0, columnspan=3, sticky='w', pady=(0, 6))

        rgb_row = tk.Frame(ci, bg=self.CARD)
        rgb_row.grid(row=6, column=0, columnspan=3, sticky='w')

        self.red_button = ttk.Checkbutton(
            rgb_row, text="Red",
            variable=self.show_red, command=self.update_image)
        self.red_button.pack(side='left', padx=(0, 10))

        self.green_button = ttk.Checkbutton(
            rgb_row, text="Green",
            variable=self.show_green, command=self.update_image)
        self.green_button.pack(side='left', padx=(0, 10))

        self.blue_button = ttk.Checkbutton(
            rgb_row, text="Blue",
            variable=self.show_blue, command=self.update_image)
        self.blue_button.pack(side='left')

        # ── Preview card ────────────────────────────────────────────────────
        prev_card = self._card(wrap)
        prev_card.grid(row=2, column=1, sticky='nsew')

        pi = tk.Frame(prev_card, bg=self.CARD)
        pi.pack(fill='both', expand=True, padx=10, pady=10)
        pi.grid_rowconfigure(0, weight=1)
        pi.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(pi, bg=self.CARD,
                                highlightthickness=0, cursor='crosshair')
        v_scroll = ttk.Scrollbar(pi, orient='vertical',
                                 command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(pi, orient='horizontal',
                                 command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set,
                              xscrollcommand=h_scroll.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        # Placeholder text (removed automatically once an image is displayed)
        self.canvas.create_text(
            400, 280,
            text="Open a BMP image to preview it here.",
            fill=self.MUTED, font=('Segoe UI', 11),
            anchor='center', tags='placeholder')
        self.canvas.bind('<Configure>', self._on_canvas_resize)

    def _on_canvas_resize(self, event):
        """Keep the placeholder centred when the canvas is resized."""
        items = self.canvas.find_withtag('placeholder')
        if items:
            self.canvas.coords(items[0], event.width / 2, event.height / 2)

    # ── Inline loading indicator ─────────────────────────────────────────────
    def _start_loading(self, message):
        """Disable action buttons and show spinner + message in the toolbar."""
        for btn in self._action_buttons:
            btn.config(state='disabled')
        self._loading_label.config(text=message)
        self._loading_frame.pack(side='left', padx=(20, 0))
        self._spin_state = {'angle': 0, 'job': None, 'alive': True}
        self._spin_tick()

    def _spin_tick(self):
        if not self._spin_state.get('alive'):
            return
        self._spin_canvas.delete('arc')
        self._spin_canvas.create_arc(
            1, 1, 17, 17,
            start=self._spin_state['angle'], extent=270,
            outline=self.ACCENT, width=3,
            style='arc', tags='arc')
        self._spin_state['angle'] = (self._spin_state['angle'] + 15) % 360
        self._spin_state['job']   = self._spin_canvas.after(40, self._spin_tick)

    def _stop_loading(self):
        """Stop spinner, hide it, and re-enable action buttons."""
        if hasattr(self, '_spin_state'):
            self._spin_state['alive'] = False
            if self._spin_state.get('job'):
                try:
                    self._spin_canvas.after_cancel(self._spin_state['job'])
                except Exception:
                    pass
        self._loading_frame.pack_forget()
        for btn in self._action_buttons:
            btn.config(state='normal')

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Select BMP File",
            filetypes=[("BMP files", "*.bmp"), ("All files", "*.*")]
        )

        if file_path:
            if not file_path.lower().endswith('.bmp'):
                messagebox.showerror("Error", "Please select a BMP file")
                return

            try:
                with open(file_path, "rb") as f:
                    header = f.read(2)
                    if header != b'BM':
                        messagebox.showerror("Error", "Invalid BMP file format")
                        return
            except Exception as e:
                messagebox.showerror("Error", f"Cannot read file: {str(e)}")
                return

            if self.parser.parse_bmp(file_path):
                self.original_image = self.parser.pixel_data.copy()
                self.display_metadata()
                self.update_image()

    def display_metadata(self):
        self.meta_vars['File Size'].set(f"{self.parser.file_size:,} bytes")
        self.meta_vars['Width'].set(f"{self.parser.width} px")
        self.meta_vars['Height'].set(f"{self.parser.height} px")
        self.meta_vars['Bit Depth'].set(f"{self.parser.bits_per_pixel} bpp")
        self.comp_result_label.config(text='')

    def numpy_to_photoimage(self, image_array):
        height, width, channels = image_array.shape
        ppm_header = f'P6\n{width} {height}\n255\n'
        ppm_data = ppm_header.encode('ascii') + image_array.tobytes()
        photo = tk.PhotoImage(data=ppm_data, format='PPM')
        return photo

    def update_image(self, event=None):
        if self.original_image is None:
            return

        self.brightness_label.config(text=f"{int(self.brightness_var.get())}%")
        self.scale_label.config(text=f"{int(self.scale_var.get())}%")

        image = self.original_image.copy().astype(np.float32)

        if not self.show_red.get():
            image[:, :, 0] = 0
        if not self.show_green.get():
            image[:, :, 1] = 0
        if not self.show_blue.get():
            image[:, :, 2] = 0

        brightness_factor = self.brightness_var.get() / 100.0
        image = np.multiply(image, brightness_factor)
        image = np.clip(image, 0, 255).astype(np.uint8)

        scale_factor = self.scale_var.get() / 100.0
        if scale_factor != 1.0:
            image = self.scale_image(image, scale_factor)

        self.current_image = image
        self.display_on_canvas()

    def scale_image(self, image, scale_factor):
        if scale_factor == 0:
            return np.zeros((1, 1, 3), dtype=np.uint8)

        old_h, old_w = image.shape[:2]
        new_h = max(1, int(old_h * scale_factor))
        new_w = max(1, int(old_w * scale_factor))

        if new_h == old_h and new_w == old_w:
            return image.copy()

        row_ratio = old_h / new_h
        col_ratio = old_w / new_w

        result  = np.zeros((new_h, new_w, 3), dtype=np.uint8)
        row_idx = (np.arange(new_h) * row_ratio).astype(int)
        col_idx = (np.arange(new_w) * col_ratio).astype(int)
        result[:, :] = image[row_idx[:, None], col_idx]
        return result

    def display_on_canvas(self):
        if self.current_image is None:
            return

        try:
            self.photo_image = self.numpy_to_photoimage(self.current_image)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display image: {str(e)}")

    def compress_image(self):
        """Compress the current BMP image and save as .custom_compressed"""
        if self.original_image is None:
            messagebox.showerror("Error", "No image loaded to compress")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Compressed Image",
            defaultextension=".custom_compressed",
            filetypes=[("custom_compressed files", "*.custom_compressed"), ("All files", "*.*")]
        )

        if not file_path:
            return

        self._start_loading("Compressing image…")
        result = {}

        def _worker():
            try:
                start_time         = time.time()
                compressor         = CompressionEngine(block_size=4096)
                compression_result = compressor.compress_data(self.original_image)

                custom_compressed_data = {
                    'width':              self.parser.width,
                    'height':             self.parser.height,
                    'bits_per_pixel':     self.parser.bits_per_pixel,
                    'original_shape':     self.original_image.shape,
                    'compression_result': compression_result,
                    'color_table':        self.parser.color_table,
                    'original_file_size': self.parser.file_size,
                }

                with open(file_path, 'wb') as f:
                    pickle.dump(custom_compressed_data, f)

                compression_time  = int((time.time() - start_time) * 1000)
                original_size     = self.parser.file_size
                compressed_size   = os.path.getsize(file_path)
                compression_ratio = original_size / compressed_size if compressed_size > 0 else 0
                space_savings     = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

                result.update(ok=True,
                              compression_time=compression_time,
                              original_size=original_size,
                              compressed_size=compressed_size,
                              compression_ratio=compression_ratio,
                              space_savings=space_savings)
            except Exception as e:
                result.update(ok=False, error=str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

        def _poll():
            if t.is_alive():
                self.root.after(50, _poll)
                return
            self._stop_loading()
            if not result.get('ok'):
                messagebox.showerror("Error", f"Compression failed: {result.get('error', 'Unknown error')}")
                return
            original_size     = result['original_size']
            compressed_size   = result['compressed_size']
            compression_ratio = result['compression_ratio']
            space_savings     = result['space_savings']
            compression_time  = result['compression_time']
            messagebox.showinfo("Compression Results", (
                f"Compression Complete!\n\n"
                f"Original BMP file size:  {original_size} bytes\n"
                f"Compressed file size:    {compressed_size} bytes\n"
                f"Compression ratio:       {compression_ratio:.4f}\n"
                f"Space savings:           {space_savings:.1f}%\n"
                f"Compression time:        {compression_time} ms"
            ))
            self.comp_result_label.config(
                text=(f"Compressed: {compressed_size:,} B  ·  "
                      f"{space_savings:.1f}% saved  ·  {compression_time} ms")
            )

        self.root.after(50, _poll)

    def open_custom_compressed_file(self):
        """Open and decompress a .custom_compressed file"""
        file_path = filedialog.askopenfilename(
            title="Open custom_compressed File",
            filetypes=[("custom_compressed files", "*.custom_compressed"), ("All files", "*.*")]
        )

        if not file_path:
            return

        self._start_loading("Decompressing image…")
        result = {}

        def _worker():
            try:
                with open(file_path, 'rb') as f:
                    custom_compressed_data = pickle.load(f)

                compression_result = custom_compressed_data['compression_result']
                original_shape     = custom_compressed_data['original_shape']
                compressor         = CompressionEngine(block_size=4096)
                decompressed_image = compressor.decompress_data(
                    compression_result, original_shape
                )
                result.update(ok=True,
                              data=custom_compressed_data,
                              image=decompressed_image)
            except Exception as e:
                result.update(ok=False, error=str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

        def _poll():
            if t.is_alive():
                self.root.after(50, _poll)
                return
            self._stop_loading()
            if not result.get('ok'):
                messagebox.showerror("Error", f"Failed to open .custom_compressed file: {result.get('error', 'Unknown error')}")
                return

            custom_compressed_data = result['data']
            decompressed_image     = result['image']

            self.parser.width          = custom_compressed_data['width']
            self.parser.height         = custom_compressed_data['height']
            self.parser.bits_per_pixel = custom_compressed_data['bits_per_pixel']
            self.parser.color_table    = custom_compressed_data.get('color_table', [])

            if 'original_file_size' in custom_compressed_data:
                self.parser.file_size = custom_compressed_data['original_file_size']
            else:
                if self.parser.bits_per_pixel <= 8:
                    row_size                = ((self.parser.bits_per_pixel * self.parser.width + 31) // 32) * 4
                    pixel_data_size         = row_size * self.parser.height
                    color_table_size        = (2 ** self.parser.bits_per_pixel) * 4
                    estimated_original_size = 54 + color_table_size + pixel_data_size
                else:
                    row_size                = ((24 * self.parser.width + 31) // 32) * 4
                    pixel_data_size         = row_size * self.parser.height
                    estimated_original_size = 54 + pixel_data_size
                self.parser.file_size = estimated_original_size

            self.parser.pixel_data = decompressed_image
            self.original_image    = decompressed_image.copy()
            self.display_metadata()
            self.update_image()

            messagebox.showinfo("Decompression Successful", (
                f"Successfully decompressed {os.path.basename(file_path)}\n\n"
                f"Reconstructed Image Properties:\n"
                f"Width:           {self.parser.width} pixels\n"
                f"Height:          {self.parser.height} pixels\n"
                f"Bits Per Pixel:  {self.parser.bits_per_pixel} bits\n"
                f"Original Size:   {self.parser.file_size} bytes"
            ))

        self.root.after(50, _poll)


def main():
    root = tk.Tk()  # Create the main application window
    app = BMPViewer(root)   # Initialize the BMPViewer with the main window
    root.mainloop() # Start the Tkinter event loop to run the application

if __name__ == "__main__":
    main()