from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import os
import requests
import uuid
import base64
import traceback
from queue import Queue
from threading import Thread

app = Flask(__name__)
CORS(app)  # Allow requests from frontend (Netlify)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

OUTPUT_FOLDER = "generated_images"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Create request queue
request_queue = Queue()
result_store = {}

def generate_images(prompt, num_images=4):
    image_urls = []
    for _ in range(num_images):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["Text", "Image"]}
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

# Worker function that runs in a background thread
def worker():
    while True:
        job_id, prompt = request_queue.get()
        try:
            image_urls = generate_images(prompt)
            result_store[job_id] = image_urls
        except Exception as e:
            result_store[job_id] = f"ERROR: {str(e)}"
        request_queue.task_done()

# Start the worker thread
Thread(target=worker, daemon=True).start()

@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    try:
        data = request.get_json()
        business_name = data.get("businessname")
        slogan = data.get("slogan", "")
        industry = data.get("industry")

        if not business_name or not industry:
            return jsonify({"error": "Business name and Industry are required."}), 400

        # Prompt creation
        prompt = f"I need a colorful traditional logo for my {industry} brand named {business_name}. Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. Play with the brand name and the icon. White background. In {industry} industry logo style. Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. Remember on a white background."
        if slogan.strip():
            prompt += f" My business slogan is {slogan}"

        # Generate a unique job ID
        job_id = str(uuid.uuid4())

        # Queue the request
        request_queue.put((job_id, prompt))

        # Wait until result is ready
        while job_id not in result_store:
            pass

        result = result_store.pop(job_id)

        if isinstance(result, str) and result.startswith("ERROR"):
            return jsonify({"error": result}), 500

        full_urls = [request.host_url.rstrip("/") + url for url in result]
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
import threading  # ✅ for request locking

app = Flask(__name__)
CORS(app)

# ✅ Lock to prevent concurrent generation
generation_lock = threading.Lock()

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
        # ✅ Ensure only one request runs generate_images at a time
        with generation_lock:
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
    app.run(debug=True)  # ❌ not for production, use Gunicorn instead

'''






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
