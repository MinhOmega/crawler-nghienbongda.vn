import cv2
import os
import dlib
import numpy as np

def blur_faces(image_path, output_path):
    # Load the image
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"Failed to load image: {image_path}")
        return
    
    # Load the pre-trained face detector from dlib
    detector = dlib.get_frontal_face_detector()
    
    # Convert the image to RGB (dlib uses RGB images)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Detect faces in the image
    faces = detector(rgb_image, 1)
    
    # Apply Gaussian blur to each face using an elliptical mask
    for face in faces:
        x, y, w, h = (face.left(), face.top(), face.width(), face.height())
        
        # Create an elliptical mask for the face
        mask = np.zeros_like(image, dtype=np.uint8)
        center = (x + w // 2, y + h // 2)
        axes = (w // 2, h // 2)
        cv2.ellipse(mask, center, axes, angle=0, startAngle=0, endAngle=360, color=(255, 255, 255), thickness=-1)

        # Create a blurred version of the entire image
        blurred_image = cv2.GaussianBlur(image, (99, 99), 30)
        
        # Combine the blurred face with the original image using the mask
        mask_inv = cv2.bitwise_not(mask)
        image_face_only = cv2.bitwise_and(blurred_image, mask)
        background = cv2.bitwise_and(image, mask_inv)
        image = cv2.add(background, image_face_only)
    
    # Save the output image
    cv2.imwrite(output_path, image)
    print(f"Processed image saved to: {output_path}")

def process_directory(input_dir, output_dir):
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Process each folder and image in the input directory
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith(('.png', '.jpg', '.jpeg')):
                input_path = os.path.join(root, file)
                relative_path = os.path.relpath(input_path, input_dir)
                output_path = os.path.join(output_dir, relative_path)
                
                # Ensure the output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Process the image to blur faces
                blur_faces(input_path, output_path)
                print(f"Processed {file}")

if __name__ == "__main__":
    input_directory = 'images'  # Directory containing the images to process
    output_directory = 'blurred_images'  # Directory to save the blurred images
    
    process_directory(input_directory, output_directory)
