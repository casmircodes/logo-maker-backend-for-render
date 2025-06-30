from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import uuid
import traceback
import base64

app = Flask(__name__, static_folder='generated_images', static_url_path='/generated_images')
CORS(app)  # Enable CORS for all domains

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it before running the application.")

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
API_ENDPOINT = f"{API_BASE_URL}/{MODEL_NAME}:generateContent"

OUTPUT_FOLDER = "generated_images"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def generate_image_with_gemini(prompt, num_images=4):
    filenames = []
    for _ in range(num_images):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["Text", "Image"],
                }
            }
            params = {"key": GOOGLE_API_KEY}
            response = requests.post(API_ENDPOINT, json=payload, params=params)
            response.raise_for_status()
            response_json = response.json()

            if (
                "candidates" in response_json
                and response_json["candidates"]
                and "content" in response_json["candidates"][0]
                and "parts" in response_json["candidates"][0]["content"]
            ):
                parts = response_json["candidates"][0]["content"]["parts"]
                for part in parts:
                    if "inlineData" in part and "data" in part["inlineData"]:
                        image_data = part["inlineData"]["data"]
                        filename = f"image_{uuid.uuid4().hex}.png"
                        filepath = os.path.join(OUTPUT_FOLDER, filename)
                        with open(filepath, "wb") as f:
                            f.write(base64.b64decode(image_data))
                        filenames.append(filename)
                        break
        except Exception as e:
            print("Error:", e)
            print(traceback.format_exc())
    return filenames

@app.route('/generate-logos', methods=["POST"])
def generate_logos():
    data = request.get_json()
    businessname = data.get("businessname", "").strip()
    slogan = data.get("slogan", "").strip()
    industry = data.get("industry", "").strip()

    if not businessname or not industry:
        return jsonify({"error": "Business name and Industry are required."}), 400

    if slogan == "":
        prompt = f"I need a colorful traditional logo for my {industry} brand named {businessname}. Use matured and professional colors. Make it attractive and tempting. White background. In {industry} industry logo style. Follow 60, 30, 10 color principle. Clear and meaningful logo icon."
    else:
        prompt = f"I need a colorful traditional logo for my {industry} brand named {businessname}. My slogan is {slogan}. Use matured and professional colors. Make it attractive and tempting. White background. In {industry} industry logo style. Follow 60, 30, 10 color principle. Clear and meaningful logo icon."

    try:
        filenames = generate_image_with_gemini(prompt)
        image_urls = [f"/generated_images/{name}" for name in filenames]
        return jsonify({"images": image_urls})
    except Exception as e:
        print("Internal Error:", e)
        return jsonify({"error": "Internal server error. Try again later."}), 500

@app.route('/generated_images/<filename>')
def serve_image(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True)
