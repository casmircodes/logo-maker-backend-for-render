from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import uuid
import base64
import traceback
import threading # Import threading for the semaphore

app = Flask(__name__)
CORS(app)  # Allow requests from frontend (Netlify)

# Retrieve Google API Key from environment variables
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

# Define the model name and API endpoint for image generation
MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

# Define the folder to save generated images and ensure it exists
OUTPUT_FOLDER = "generated_images"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Create a semaphore with a value of 1.
# This semaphore acts as a mutex, ensuring that only one thread can acquire it at a time.
# Subsequent requests attempting to acquire it will block and wait until it's released,
# effectively creating a queue for the logo generation process.
generation_semaphore = threading.Semaphore(1)


def generate_images(prompt, num_images=4):
    """
    Generates images based on the given prompt using the Google Generative Language API.
    Saves the generated images locally and returns their URLs.

    Args:
        prompt (str): The text prompt for image generation.
        num_images (int): The number of images to generate. Defaults to 4.

    Returns:
        list: A list of URLs for the generated images.
    """
    image_urls = []

    for i in range(num_images):
        try:
            # Construct the payload for the image generation API request
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["Text", "Image"]
                }
            }

            # Make the API call to generate content (which includes images)
            response = requests.post(API_ENDPOINT, json=payload, params={"key": GOOGLE_API_KEY})
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            data = response.json()

            # Extract image data from the API response
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    image_data = part["inlineData"]["data"]
                    # Generate a unique filename for the image
                    filename = f"image_{uuid.uuid4().hex}.png"
                    filepath = os.path.join(OUTPUT_FOLDER, filename)
                    # Decode base64 image data and save it to a file
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(image_data))

                    # Construct the URL for the saved image
                    image_url = f"/generated_images/{filename}"
                    image_urls.append(image_url)
                    break  # Assuming one image per API call for simplicity, break after first image found
        except Exception as e:
            # Log any errors during image generation for debugging purposes
            print(f"Image generation error for image {i+1}: {e}\n{traceback.format_exc()}")
            continue  # Continue to try generating other images if one fails

    return image_urls


@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    """
    Handles requests to generate logos.
    This endpoint ensures that only one logo generation request is processed at a time.
    Subsequent requests will wait until the current one completes.
    """
    # Attempt to acquire the semaphore.
    # If the semaphore is already held by another request, this call will block
    # until the semaphore is released, effectively putting the current request in a waiting queue.
    print("Attempting to acquire semaphore for logo generation...")
    generation_semaphore.acquire()
    print("Semaphore acquired. Processing logo generation request.")

    try:
        # Parse the JSON data from the incoming request
        data = request.get_json()
        business_name = data.get("businessname")
        slogan = data.get("slogan", "")
        industry = data.get("industry")

        # Validate required input fields
        if not business_name or not industry:
            return jsonify({"error": "Business name and Industry are required."}), 400

        # Dynamically create the prompt for image generation based on user input
        prompt = (
            f"I need a colorful traditional logo for my {industry} brand named {business_name}. "
            f"Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. "
            f"Play with the brand name and the icon. White background. In {industry} industry logo style. "
            f"Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. "
            f"Remember on a white background."
        )

        if slogan.strip():
            prompt += f" My business slogan is {slogan}"

        # Call the image generation function to get logo images
        image_urls = generate_images(prompt)

        # Check if any images were successfully generated
        if not image_urls:
            return jsonify({"error": "Failed to generate images."}), 500

        # Prepend the host URL to make image URLs absolute for the client
        full_urls = [request.host_url.rstrip("/") + url for url in image_urls]
        return jsonify({"images": full_urls})

    except Exception as e:
        # Catch any unexpected errors during request processing and return a server error
        print(f"Server error in generate_logo: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    finally:
        # Ensure the semaphore is released after the request is processed,
        # regardless of whether it succeeded or failed. This allows the next waiting request to proceed.
        print("Releasing semaphore.")
        generation_semaphore.release()


@app.route("/generated_images/<filename>")
def serve_image(filename):
    """
    Serves static image files from the 'generated_images' directory.
    This endpoint allows clients to retrieve the generated logo images.
    """
    return send_from_directory(OUTPUT_FOLDER, filename)


if __name__ == "__main__":
    # Run the Flask application.
    # In a production environment, it's recommended to use a production-ready WSGI server
    # like Gunicorn instead of Flask's built-in development server.
    app.run(debug=True)








'''
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import uuid
import base64
import traceback
import threading
import time

app = Flask(__name__)
CORS(app)  # Allow requests from frontend (Netlify)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

OUTPUT_FOLDER = "generated_images"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Lock to ensure one request at a time
generation_lock = threading.Lock()

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
    """Main endpoint: Used internally by /waiting-generate-logo after lock is acquired."""
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


@app.route("/waiting-generate-logo", methods=["POST"])
def waiting_generate_logo():
    """Queue requests here. Only one enters generate-logo at a time."""
    # Wait until lock is free, then enter
    with generation_lock:
        print("Processing a queued request...")
        time.sleep(60)
        return generate_logo()


@app.route("/generated_images/<filename>")
def serve_image(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)

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
