from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import replicate
import uuid
import base64
import requests
import traceback

app = Flask(__name__)
CORS(app)

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
if not REPLICATE_API_TOKEN:
    raise ValueError("REPLICATE_API_TOKEN environment variable not set.")

replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

MODEL_VERSION = "google/imagen-3-fast"  # The model slug on Replicate

OUTPUT_FOLDER = "generated_images"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def generate_images(prompt, num_images=1):
    image_urls = []

    for _ in range(num_images):
        try:
            output = replicate_client.run(
                MODEL_VERSION,
                input={"prompt": prompt}
            )

            if not output or not isinstance(output, list):
                continue

            # output is a list of URLs (usually one image per call)
            image_url = output[0]
            image_response = requests.get(image_url)
            if image_response.status_code == 200:
                filename = f"image_{uuid.uuid4().hex}.png"
                filepath = os.path.join(OUTPUT_FOLDER, filename)
                with open(filepath, "wb") as f:
                    f.write(image_response.content)
                image_urls.append(f"/generated_images/{filename}")
        except Exception as e:
            print(f"Image generation error: {e}\n{traceback.format_exc()}")
            continue

    return image_urls

@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    try:
        data = request.get_json()
        business_name = data.get("businessname")
        slogan = data.get("slogan", "")
        industry = data.get("industry")

        if not business_name or not industry:
            return jsonify({"error": "Business name and Industry are required."}), 400

        prompt = f"I need a colorful traditional logo for my {industry} brand named {business_name}. Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. Play with the brand name and the icon. White background. In {industry} industry logo style. Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. Remember on a white background."
        if slogan.strip():
            prompt += f" My business slogan is {slogan}"

        image_urls = generate_images(prompt)

        if not image_urls:
            return jsonify({"error": "Failed to generate images."}), 500

        full_urls = [request.host_url.rstrip("/") + url for url in image_urls]
        return jsonify({"images": full_urls})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route("/generated_images/<filename>")
def serve_image(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True)










'''

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import uuid
import base64
import traceback

app = Flask(__name__)
CORS(app)  # Allow requests from frontend (Netlify)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

OUTPUT_FOLDER = "generated_images"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def generate_images(prompt, num_images=4):
    image_urls = []

    for _ in range(num_images):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["Text", "Image"]
                }
            }

            response = requests.post(API_ENDPOINT, json=payload, params={"key": GOOGLE_API_KEY})
            response.raise_for_status()
            data = response.json()

            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    image_data = part["inlineData"]["data"]
                    filename = f"image_{uuid.uuid4().hex}.png"
                    filepath = os.path.join(OUTPUT_FOLDER, filename)
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(image_data))

                    image_url = f"/generated_images/{filename}"
                    image_urls.append(image_url)
                    break
        except Exception as e:
            print(f"Image generation error: {e}\n{traceback.format_exc()}")
            continue

    return image_urls


@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    try:
        data = request.get_json()
        business_name = data.get("businessname")
        slogan = data.get("slogan", "")
        industry = data.get("industry")

        if not business_name or not industry:
            return jsonify({"error": "Business name and Industry are required."}), 400

        # Dynamic prompt creation
        prompt = f"I need a colorful traditional logo for my {industry} brand named {business_name}. Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. Play with the brand name and the icon. White background. In {industry} industry logo style. Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. Remember on a white background."

        if slogan.strip():
            prompt += f" My business slogan is {slogan}"

        image_urls = generate_images(prompt)

        if not image_urls:
            return jsonify({"error": "Failed to generate images."}), 500

        full_urls = [request.host_url.rstrip("/") + url for url in image_urls]
        return jsonify({"images": full_urls})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/generated_images/<filename>")
def serve_image(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)

'''
