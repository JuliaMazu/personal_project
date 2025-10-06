FROM python:3.12

# Create a working directory.
WORKDIR /src/app

# Install Python dependencies.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the codebase into the image
COPY . ./

# Finally, run gunicorn.
CMD [ "gunicorn", "--workers=3", "--threads=1", "-b 0.0.0.0:8050", "app:server"]