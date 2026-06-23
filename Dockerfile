# 1. Use a lightweight, official Python base image
FROM python:3.11-slim

# 2. Set environment variables to keep Python from writing buffering files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Establish our working directory inside the virtual container
WORKDIR /app

# 4. Copy the requirements layout list and install dependencies inside the container image
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy the remaining local project folders into the container file system
COPY . .

# 6. Document the internal network port exposing gateway
EXPOSE 8000

# 7. Define the primary command to launch Uvicorn when the container starts up
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]