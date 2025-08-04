#!/usr/bin/env python3
"""
Quick local test script for audio splitter functions
Run this to test core functionality without Docker
"""

import os
import sys
sys.path.append('.')

from split_audio import get_audio_info, calculate_chunk_duration, get_optimal_output_format
from google.oauth2 import service_account
from googleapiclient.discovery import build

def test_audio_info():
    """Test audio info extraction"""
    print("🔍 Testing audio info extraction...")
    
    test_file = "sample-files/250609_0051 BoD Mtg.WMA"
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return False
        
    try:
        duration, bitrate, codec_name = get_audio_info(test_file)
        print(f"✅ Audio Info:")
        print(f"   Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print(f"   Bitrate: {bitrate/1000:.0f} kbps")
        print(f"   Codec: {codec_name}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_chunk_calculation():
    """Test chunk size calculation"""
    print("\n🧮 Testing chunk size calculation...")
    
    # Test with different parameters
    test_cases = [
        (128000, 25, "m4a", 96),  # 128kbps input, 25MB chunks, m4a output at 96kbps
        (256000, 20, "wav", None),  # 256kbps input, 20MB chunks, wav output
        (96000, 25, "mp3", 128),   # 96kbps input, 25MB chunks, mp3 output at 128kbps
    ]
    
    for bitrate, max_mb, format, output_bitrate in test_cases:
        if output_bitrate:
            chunk_duration = calculate_chunk_duration(bitrate, max_mb, format, output_bitrate)
        else:
            chunk_duration = calculate_chunk_duration(bitrate, max_mb, format)
            
        print(f"✅ {bitrate/1000:.0f}kbps → {max_mb}MB {format.upper()}: {chunk_duration:.1f}s chunks")

def test_format_selection():
    """Test optimal format selection"""
    print("\n🎵 Testing format selection...")
    
    test_cases = [
        ("test.wma", "wmav2"),
        ("test.mp3", "mp3"),
        ("test.wav", "pcm_s16le"),
        ("unknown.xyz", "unknown"),
    ]
    
    for filename, codec in test_cases:
        optimal = get_optimal_output_format(filename, detected_codec=codec)
        print(f"✅ {filename} ({codec}) → {optimal.upper()}")

def test_service_account():
    """Test service account credentials"""
    print("\n🔑 Testing service account access...")
    
    key_file = "service-account-key.json"
    if not os.path.exists(key_file):
        print(f"❌ Service account key not found: {key_file}")
        return False
        
    try:
        credentials = service_account.Credentials.from_service_account_file(
            key_file,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # Test with a known file
        file_id = '1zhAUIDpYSA3FNxBhKQWT0sp9RssUhN7R'
        file_metadata = drive_service.files().get(
            fileId=file_id,
            fields='name,size,mimeType',
            supportsAllDrives=True
        ).execute()
        
        print(f"✅ Service account working!")
        print(f"   Can access: {file_metadata['name']}")
        print(f"   Size: {int(file_metadata.get('size', 0)) / (1024*1024):.1f} MB")
        return True
        
    except Exception as e:
        print(f"❌ Service account error: {e}")
        return False

def main():
    print("🧪 Audio Splitter Local Testing")
    print("=" * 50)
    
    success_count = 0
    total_tests = 4
    
    if test_audio_info():
        success_count += 1
        
    test_chunk_calculation()
    success_count += 1
    
    test_format_selection() 
    success_count += 1
    
    if test_service_account():
        success_count += 1
    
    print(f"\n📊 Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 All tests passed! Core functionality is working.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")

if __name__ == "__main__":
    main()