#!/usr/bin/env python3
"""
Test script for the AI Text Detector web application.
This script tests the Flask app without requiring the AI model to be loaded.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Flask app
from app import app

class TestAITextDetector(unittest.TestCase):
    """Test cases for the AI Text Detector web application."""
    
    def setUp(self):
        """Set up test client."""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_home_page(self):
        """Test that the home page loads correctly."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AI Text Detector', response.data)
        self.assertIn(b'Analyze your content', response.data)
    
    def test_analyze_text_endpoint(self):
        """Test the text analysis endpoint."""
        # Mock the model loading and prediction functions
        with patch('app.load_model') as mock_load_model, \
             patch('app.predict_single_text') as mock_predict:
            
            # Configure mocks
            mock_load_model.return_value = True
            mock_predict.return_value = (0.75, 1)  # 75% AI probability, classified as AI
            
            # Test text analysis
            test_text = "This is a test text for AI detection."
            response = self.app.post('/analyze', 
                                   data={'text': test_text},
                                   content_type='application/x-www-form-urlencoded')
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            
            # Check response structure
            self.assertIn('segments', data)
            self.assertIn('statistics', data)
            self.assertIn('overall_assessment', data)
            
            # Check statistics
            stats = data['statistics']
            self.assertIn('total_length', stats)
            self.assertIn('ai_percentage', stats)
            self.assertIn('human_percentage', stats)
            self.assertIn('avg_ai_probability', stats)
    
    def test_analyze_empty_text(self):
        """Test handling of empty text input."""
        response = self.app.post('/analyze', 
                               data={'text': ''},
                               content_type='application/x-www-form-urlencoded')
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('error', data)
        self.assertIn('No text provided', data['error'])
    
    def test_analyze_file_upload(self):
        """Test file upload functionality."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is test content for file upload.")
            temp_file_path = f.name
        
        try:
            # Mock the model functions
            with patch('app.load_model') as mock_load_model, \
                 patch('app.predict_single_text') as mock_predict:
                
                mock_load_model.return_value = True
                mock_predict.return_value = (0.25, 0)  # 25% AI probability, classified as human
                
                # Test file upload
                with open(temp_file_path, 'rb') as f:
                    response = self.app.post('/analyze',
                                           data={'file': (f, 'test.txt')},
                                           content_type='multipart/form-data')
                
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertIn('segments', data)
                self.assertIn('statistics', data)
        
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    def test_model_not_available(self):
        """Test handling when AI model is not available."""
        with patch('app.load_model') as mock_load_model:
            mock_load_model.return_value = False
            
            response = self.app.post('/analyze',
                                   data={'text': 'Test text'},
                                   content_type='application/x-www-form-urlencoded')
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            # Should return default values when model is not available
            self.assertEqual(data['segments'][0]['probability'], 0.0)
    
    def test_large_text_handling(self):
        """Test handling of large text input."""
        # Create a large text (simulate)
        large_text = "Test text. " * 1000  # ~6000 characters
        
        with patch('app.load_model') as mock_load_model, \
             patch('app.predict_single_text') as mock_predict:
            
            mock_load_model.return_value = True
            mock_predict.return_value = (0.5, 1)
            
            response = self.app.post('/analyze',
                                   data={'text': large_text},
                                   content_type='application/x-www-form-urlencoded')
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn('segments', data)
            # Should have multiple segments for large text
            self.assertGreater(len(data['segments']), 1)

def test_flask_app_structure():
    """Test that the Flask app has the correct structure."""
    # Test that required routes exist
    with app.test_client() as client:
        # Test home route
        response = client.get('/')
        assert response.status_code == 200
        
        # Test analyze route exists (should return 405 for GET)
        response = client.get('/analyze')
        assert response.status_code == 405  # Method not allowed for GET

if __name__ == '__main__':
    print("Testing AI Text Detector Web Application...")
    print("=" * 50)
    
    # Run basic structure test
    try:
        test_flask_app_structure()
        print("✓ Flask app structure test passed")
    except Exception as e:
        print(f"✗ Flask app structure test failed: {e}")
    
    # Run unit tests
    print("\nRunning unit tests...")
    unittest.main(verbosity=2, exit=False)
    
    print("\n" + "=" * 50)
    print("Test completed!") 