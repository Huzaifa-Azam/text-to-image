# Import necessary libraries
import grpc
from concurrent import futures
import time
import text2img_pb2
import text2img_pb2_grpc
import requests
import os
import base64

# WebUI API endpoint for Stable Diffusion or similar text-to-image model
WEBUI_API_URL = "http://127.0.0.1:7860/sdapi/v1/txt2img"

# Directory to save generated images
SAVE_DIR = "./generated_images"

# Define the gRPC service class by inheriting from the generated servicer class
class Text2ImgService(text2img_pb2_grpc.Text2ImgServiceServicer):
    
    # Define the main service method that will handle image generation requests
    def GenerateImages(self, request, context):
        responses = []

        # Create the directory if it doesn't exist
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)

        # Process each prompt in the request
        for prompt_obj in request.prompts:
            prompt = prompt_obj.prompt.strip()

            # Check for empty prompt
            if not prompt:
                responses.append(text2img_pb2.ImageResponse(
                    success_code="400",
                    image_path="Error: Prompt cannot be empty."
                ))
                continue

            # Check for overly long prompts
            if len(prompt) > 500:
                responses.append(text2img_pb2.ImageResponse(
                    success_code="400",
                    image_path="Error: Prompt exceeds maximum allowed length (500 characters)."
                ))
                continue

            # Payload for the model server
            payload = {
                "prompt": prompt,
                "steps": 20  # You can tune this parameter for quality/speed trade-off
            }

            try:
                # Send a POST request to the model server
                response = requests.post(WEBUI_API_URL, json=payload, timeout=10000)

                # If the server response is not OK, return an error
                if response.status_code != 200:
                    responses.append(text2img_pb2.ImageResponse(
                        success_code=str(response.status_code),
                        image_path=f"Error: Failed to generate image. Status code {response.status_code}"
                    ))
                    continue

                # Parse the response JSON
                result = response.json()

                # Validate the image content in response
                if 'images' not in result or not result['images']:
                    responses.append(text2img_pb2.ImageResponse(
                        success_code="500",
                        image_path="Error: No image returned by the model."
                    ))
                    continue

                # Decode base64 image data
                image_base64 = result['images'][0]
                filename = f"{int(time.time() * 1000)}.png"  # Unique filename using timestamp
                image_path = os.path.join(SAVE_DIR, filename)

                # Save the image to disk
                with open(image_path, "wb") as f:
                    f.write(base64.b64decode(image_base64))

                # Add a successful response
                responses.append(text2img_pb2.ImageResponse(
                    success_code="200",
                    image_path=image_path
                ))

                time.sleep(0.5)  # Delay to prevent file overwrite due to same timestamp

            # Handle network-related errors
            except requests.exceptions.RequestException as e:
                responses.append(text2img_pb2.ImageResponse(
                    success_code="503",
                    image_path=f"Error: Model server unavailable. {str(e)}"
                ))

            # Handle unexpected errors
            except Exception as e:
                responses.append(text2img_pb2.ImageResponse(
                    success_code="500",
                    image_path=f"Error: Unexpected server error. {str(e)}"
                ))

        # Return the list of image responses
        return text2img_pb2.ImageResponseList(images=responses)


# Function to start the gRPC server
def serve():
    # Create a gRPC server with a thread pool executor
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=15))
    
    # Register the service with the server
    text2img_pb2_grpc.add_Text2ImgServiceServicer_to_server(Text2ImgService(), server)
    
    # Listen on port 50051
    server.add_insecure_port('[::]:50051')
    
    # Start the server
    server.start()
    print("gRPC server running on port 50051...")
    
    # Keep the server running
    server.wait_for_termination()

# Entry point
if __name__ == "__main__":
    serve()
