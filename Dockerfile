# Use an official Python 3.11 slim image for better prformance
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
# default timezone (can override with docker run -e TZ=UTC)
ENV TZ=Asia/Tehran


# Set the working directory in the container
WORKDIR /app

# Copy the NTP server code into the container
COPY ntp_server.py .
# Copy the healthcheck into the container
COPY healthcheck.py .

# Expose UDP port 123 (the standard NTP port)
EXPOSE 123/udp

# Define healthcheck (runs every 30s, 5s timeout, 3 retries)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
  CMD python healthcheck.py || exit 1

# Run the NTP server script
CMD ["python","-u","ntp_server.py"]
