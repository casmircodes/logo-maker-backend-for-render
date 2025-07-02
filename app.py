from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import requests
import uuid
import traceback
import base64
from threading import Lock

app = Flask(__name__, static_folder='generated_images', static_url_path='/generated_images')

# Set up a lock to ensure one request at a time
generation_lock = Lock()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY environment variable not set. "
        "Please set it before running the application."
    )

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

            if "error" in response_json:
                error_message = response_json["error"].get("message", "Unknown error from Gemini API")
                print(f"Gemini API Error: {error_message}")
                continue

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
            print(f"Error: {traceback.format_exc()}")
    return filenames


@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    """
    API endpoint to receive data and return generated image filenames.
    """
    try:
        data = request.get_json()
        business_name = data.get("businessname", "")
        slogan = data.get("slogan", "")
        industry = data.get("industry", "")

        if not business_name or not industry:
            return jsonify({"error": "Business name and industry are required."}), 400

        if slogan.strip() == "":
            main_prompt = (
                f"I need a colorful traditional logo for my {industry} brand named {business_name}. "
                f"Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. "
                f"Play with the brand name and the icon. White background. In {industry} industry logo style. "
                f"Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. "
                f"Remember on a white background."
            )
        else:
            main_prompt = (
                f"I need a colorful traditional logo for my {industry} brand named {business_name}. "
                f"Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. "
                f"Play with the brand name and the icon. White background. In {industry} industry logo style. "
                f"Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. "
                f"My business slogan is {slogan}. Remember on a white background."
            )

        # Ensure one request at a time
        with generation_lock:
            filenames = generate_image_with_gemini(main_prompt)

        if not filenames:
            return jsonify({"error": "Image generation failed. Try again."}), 500

        image_urls = [f"/generated_images/{filename}" for filename in filenames]
        return jsonify({"images": image_urls}), 200

    except Exception as e:
        print(f"Unexpected error: {traceback.format_exc()}")
        return jsonify({"error": "An unexpected error occurred."}), 500


@app.route('/generated_images/<filename>')
def serve_image(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


@app.route("/")
def home():
    return jsonify({"message": "Welcome to Brandice AI Logo Generator API"})


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
