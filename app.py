from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, jsonify
import math
import os
import wave
import csv
from datetime import datetime
from elevenlabs import generate, save, set_api_key
from pydub import AudioSegment, silence
from pydub.silence import split_on_silence
from audiostretchy.stretch import stretch_audio
import soundfile as sf

set_api_key("ELEVENLABS-API-KEY")

app = Flask(__name__)

path = '/home/florianvo/copycheck/output/'

def create_audio(target_duration, text, voice):
    if voice == "f":
        voice_name = "Matilda"
    elif voice =="m":
        voice_name = "Liam"

    target_duration -= 0.5  # Subtract .5 second from the target_duration
    audio = generate(text, voice=voice_name, model="eleven_multilingual_v2")

     # Print the current working directory for debugging
    print("Current working directory: " + os.getcwd())

    # Define the full path to the output directory
    output_dir = os.path.join(os.getcwd(), 'copycheck/output/')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define the full path to the output file
    output_file = os.path.join(output_dir, 'output.wav')

    # Now you can safely save the file
    save(audio, output_file)

    # Load the audio file
    y, sr = sf.read(path + 'output.wav')

    # Resave the audio file
    sf.write(path + 'output.wav', y, sr)

    audio_segment = AudioSegment.from_wav(path + "output.wav")
    chunks = split_on_silence(audio_segment, min_silence_len=50, silence_thresh=-40)
    processed_audio = sum(chunks)

    processed_audio.export(path + "output.wav", format="wav")

    duration = len(processed_audio) / 1000.0  # Duration in seconds
    stretch_factor = min(max(duration / target_duration, 1), 2)  # Ensure stretch_factor is between 1 and 2

    if stretch_factor > 1:
        stretch_audio(path + "output.wav", path + "output-sped.wav", ratio=1/stretch_factor)

    stretched_audio = AudioSegment.from_wav(path + "output-sped.wav")
    trimmed_audio = sum(split_on_silence(stretched_audio, min_silence_len=1000, silence_thresh=-40))  # Adjust silence_thresh if needed

    half_second_silence = AudioSegment.silent(duration=250)  # 500 milliseconds of silence

    final_audio = half_second_silence + trimmed_audio + half_second_silence
    final_audio.export(path + "output-sped.wav", format="wav")

    # Create a timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    date = datetime.now().strftime("%Y%m%d")

    # Create a new directory with the current date if it doesn't exist
    new_path = os.path.join(path, date)
    if not os.path.exists(new_path):
        os.makedirs(new_path)

    # Change the file saving to use the new timestamped names
    original_file_path = os.path.join(new_path, f"vo-{timestamp}.mp3")
    sped_up_file_path = os.path.join(new_path, f"vo-sped-{timestamp}.mp3")

    # Convert WAV to MP3 and save
    AudioSegment.from_wav(path + "output.wav").export(original_file_path, format="mp3")
    if stretch_factor > 1:
        AudioSegment.from_wav(path + "output-sped.wav").export(sped_up_file_path, format="mp3")

    rec_duration_min = math.ceil(max(1, duration - 2))
    rec_duration_max = math.ceil(duration + 3)

    return {
        'original': original_file_path,
        'sped_up': sped_up_file_path if stretch_factor > 1 else None,
        'rec_duration_range': f"{rec_duration_min}-{rec_duration_max}"
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_audio():
    text = request.form['text']
    target_duration = int(request.form['target_duration'])
    voice = request.form['voice']
    email_address = request.form.get('email')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Define the path to your CSV file
    csv_file_path = path + 'mails.csv'

    # Write the data to the CSV file
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([email_address, text, timestamp])

    result = create_audio(target_duration, text, voice)
    rec_duration_range = result['rec_duration_range']

    # Extract the base directory name from the full path to get a web-accessible path
    original_path = os.path.basename(result['original'])
    sped_up_path = os.path.basename(result['sped_up']) if result['sped_up'] else None

    # Construct the web-accessible paths
    web_accessible_original_path = f"/audio/{datetime.now().strftime('%Y%m%d')}/{original_path}"
    web_accessible_sped_up_path = f"/audio/{datetime.now().strftime('%Y%m%d')}/{sped_up_path}" if sped_up_path else None

    return jsonify({
        'rec_duration_range': rec_duration_range,
        'show_audio': True,
        'original': web_accessible_original_path,  # Send the web-accessible path
        'sped_up_path': web_accessible_sped_up_path  # Send the web-accessible path if it exists
    })

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    # The 'path' converter allows you to match URLs with slashes
    return send_from_directory('output', filename)

if __name__ == '__main__':
    app.run()