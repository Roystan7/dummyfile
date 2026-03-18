from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import os

app = Flask(__name__)
CORS(app)

# Folder where MP4 will be saved permanently
SAVE_FOLDER = "synopsis"

# Create folder if not exists
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

@app.route("/save_video", methods=["POST"])
def save_video():
    try:
        # Base64 video from browser
        base64_video = request.json["video"]

        # File name
        file_name = request.json.get("name", "video_synopsis.mp4")
        file_path = os.path.join(SAVE_FOLDER, file_name)

        # Remove metadata (data:video/mp4;base64,...)
        base64_data = base64_video.split(",")[1]

        # Decode
        mp4_data = base64.b64decode(base64_data)

        # Save to file
        with open(file_path, "wb") as f:
            f.write(mp4_data)

        return jsonify({
            "status": "success",
            "saved_to": file_path
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
