from rembg import remove
from PIL import Image
import os
import io

def remove_background(input_folder, output_folder):
    # Traverse through directory and subdirectories
    for subdir, dirs, files in os.walk(input_folder):
        for filename in files:
            if filename.endswith(('.png', '.jpg', '.jpeg')):  # Check for image files
                input_path = os.path.join(subdir, filename)
                
                # Determine output path and create directory if it doesn't exist
                relative_path = os.path.relpath(subdir, input_folder)
                output_subdir = os.path.join(output_folder, relative_path)
                if not os.path.exists(output_subdir):
                    os.makedirs(output_subdir)
                
                output_path = os.path.join(output_subdir, filename.rsplit('.', 1)[0] + '.png')  # Change extension to .png

                # Open the image
                with open(input_path, 'rb') as file:
                    img_data = file.read()

                # Remove background
                result = remove(img_data)

                # Save the output image
                img = Image.open(io.BytesIO(result))
                img.save(output_path, format='PNG')  # Save as PNG to preserve transparency

                print(f'Processed {output_path}')

if __name__ == "__main__":
    input_folder = 'images'  # Main input folder containing sub-folders with images
    output_folder = 'no_background_images'  # Main output folder
    remove_background(input_folder, output_folder)
