# Import necessary modules from Flask and other libraries
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import uuid
import base64
import traceback
import queue
import threading
import time # For simulating processing time if needed, can be removed

# Initialize the Flask application
app = Flask(__name__)
# Enable Cross-Origin Resource Sharing (CORS) for the application, allowing requests from different origins (e.g., a frontend hosted on Netlify)
CORS(app)

# Retrieve the Google API Key from environment variables
# This key is essential for authenticating with the Google Generative Language API
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
# Raise an error if the API key is not set, as it's a mandatory configuration
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

# Define the model name to be used for image generation
MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
# Construct the API endpoint URL using the model name
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

# Define the folder where generated images will be saved
OUTPUT_FOLDER = "generated_images"
# Create the output folder if it doesn't already exist
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- Queue and Synchronization Mechanisms ---
# A queue to hold incoming image generation requests
request_queue = queue.Queue()
# A lock to protect access to shared resources like 'is_generating' and 'request_results'
processing_lock = threading.Lock()
# A flag to indicate if an image generation process is currently active
is_generating = False
# A dictionary to store the results of processed requests, keyed by their unique request IDs
request_results = {}

# Function to generate images based on a given prompt
def generate_images(prompt, num_images=4):
    """
    Generates a specified number of images using the Google Generative Language API.

    Args:
        prompt (str): The text prompt to guide image generation.
        num_images (int): The number of images to generate.

    Returns:
        list: A list of URLs to the generated images.
    """
    image_urls = []

    for _ in range(num_images):
        try:
            # Define the payload for the API request, including the text prompt
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "image/png" # Request image directly
                }
            }

            # Send a POST request to the API endpoint with the payload and API key
            response = requests.post(API_ENDPOINT, json=payload, params={"key": GOOGLE_API_KEY})
            # Raise an HTTPError for bad responses (4xx or 5xx)
            response.raise_for_status()
            # Parse the JSON response from the API
            data = response.json()

            # Extract image data from the API response
            # The structure for image generation might differ slightly from text generation.
            # Assuming the image is directly in 'bytesBase64Encoded' in the first prediction.
            # Adjust this parsing based on the actual API response structure for image generation.
            if data and data.get("predictions"):
                for prediction in data["predictions"]:
                    if "bytesBase64Encoded" in prediction:
                        image_data = prediction["bytesBase64Encoded"]
                        # Generate a unique filename for the image
                        filename = f"image_{uuid.uuid4().hex}.png"
                        # Construct the full file path
                        filepath = os.path.join(OUTPUT_FOLDER, filename)
                        # Decode the base64 image data and save it to a file
                        with open(filepath, "wb") as f:
                            f.write(base64.b64decode(image_data))

                        # Construct the URL for the saved image
                        image_url = f"/generated_images/{filename}"
                        image_urls.append(image_url)
                        break # Only take the first image from each prediction if multiple are returned
            else:
                print("No predictions or image data found in the API response.")

        except requests.exceptions.RequestException as req_err:
            print(f"API request error: {req_err}\n{traceback.format_exc()}")
            continue
        except Exception as e:
            print(f"Image generation or file saving error: {e}\n{traceback.format_exc()}")
            continue

    return image_urls

# Function to process the next request in the queue
def process_next_in_queue():
    """
    Processes the next pending request in the queue if no other generation is active.
    This function runs in a separate thread.
    """
    global is_generating

    with processing_lock:
        # Check if no generation is currently active and the queue is not empty
        if not is_generating and not request_queue.empty():
            is_generating = True # Set flag to indicate processing has started
            # Retrieve the next request from the queue
            request_id, request_data = request_queue.get()
            print(f"Processing queued request: {request_id}")
        else:
            return # No request to process or another is already generating

    # Extract data for image generation
    business_name = request_data.get("businessname")
    slogan = request_data.get("slogan", "")
    industry = request_data.get("industry")

    # Dynamic prompt creation
    prompt = f"I need a colorful traditional logo for my {industry} brand named {business_name}. Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. Play with the brand name and the icon. White background. In {industry} industry logo style. Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. Remember on a white background."
    if slogan.strip():
        prompt += f" My business slogan is {slogan}"

    try:
        # Simulate some processing time (remove in production)
        # time.sleep(5)
        # Call the image generation function
        image_urls = generate_images(prompt)
        if not image_urls:
            result = {"error": "Failed to generate images for queued request."}
        else:
            # Convert relative URLs to full URLs
            full_urls = [request.host_url.rstrip("/") + url for url in image_urls]
            result = {"images": full_urls}
    except Exception as e:
        print(f"Error processing queued request {request_id}: {e}\n{traceback.format_exc()}")
        result = {"error": f"Server error during queued processing: {str(e)}"}

    with processing_lock:
        # Store the result for the client to retrieve
        request_results[request_id] = result
        is_generating = False # Reset flag after processing is complete

    # After processing, try to process the next item in the queue
    # This creates a chain reaction for queued items
    if not request_queue.empty():
        threading.Thread(target=process_next_in_queue).start()


# Endpoint for generating logos
@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    """
    Handles requests for logo generation. If a generation is already in progress,
    the request is queued. Otherwise, it's processed immediately.
    """
    try:
        data = request.get_json()
        business_name = data.get("businessname")
        slogan = data.get("slogan", "")
        industry = data.get("industry")

        if not business_name or not industry:
            return jsonify({"error": "Business name and Industry are required."}), 400

        # Generate a unique ID for this request
        request_id = str(uuid.uuid4())

        with processing_lock:
            if is_generating:
                # If a generation is already in progress, add the request to the queue
                request_queue.put((request_id, data))
                print(f"Request {request_id} queued.")
                return jsonify({
                    "message": "Request queued. Please use the /check-status endpoint with your request ID to get the result.",
                    "request_id": request_id
                }), 202 # 202 Accepted status
            else:
                # If no generation is in progress, start processing immediately
                global is_generating
                is_generating = True # Set flag to indicate processing has started
                print(f"Request {request_id} started processing immediately.")

        # Dynamic prompt creation
        prompt = f"I need a colorful traditional logo for my {industry} brand named {business_name}. Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. Play with the brand name and the icon. White background. In {industry} industry logo style. Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. Remember on a white background."
        if slogan.strip():
            prompt += f" My business slogan is {slogan}"

        try:
            # Call the image generation function
            image_urls = generate_images(prompt)

            if not image_urls:
                result = {"error": "Failed to generate images."}
                status_code = 500
            else:
                # Convert relative URLs to full URLs
                full_urls = [request.host_url.rstrip("/") + url for url in image_urls]
                result = {"images": full_urls}
                status_code = 200

        except Exception as e:
            print(f"Error during immediate processing of request {request_id}: {e}\n{traceback.format_exc()}")
            result = {"error": f"Server error during immediate processing: {str(e)}"}
            status_code = 500
        finally:
            with processing_lock:
                global is_generating
                is_generating = False # Reset flag after processing is complete
            # After immediate processing, check if there are queued requests to start
            if not request_queue.empty():
                threading.Thread(target=process_next_in_queue).start()

        return jsonify(result), status_code

    except Exception as e:
        print(f"Unhandled error in /generate-logo: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# Endpoint to check the status of a queued request
@app.route("/check-status/<request_id>", methods=["GET"])
def check_status(request_id):
    """
    Allows clients to check the status and retrieve the result of a previously
    queued image generation request.
    """
    with processing_lock:
        result = request_results.get(request_id)
        if result:
            # If result is available, return it and remove from storage
            del request_results[request_id]
            return jsonify(result), 200
        else:
            # If result is not yet available, indicate pending status
            return jsonify({"status": "pending", "message": "Your request is being processed or is in queue."}), 200

# Endpoint to serve generated images
@app.route("/generated_images/<filename>")
def serve_image(filename):
    """
    Serves static image files from the 'generated_images' folder.
    """
    return send_from_directory(OUTPUT_FOLDER, filename)

# Main entry point for running the Flask application
if __name__ == "__main__":
    # Run the Flask app in debug mode (for development)
    # In production, use a production-ready WSGI server like Gunicorn or uWSGI
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
