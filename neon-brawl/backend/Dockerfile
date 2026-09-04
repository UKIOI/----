FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
EXPOSE 8080
ENV APP_EDITION=internet HOST=0.0.0.0 PORT=8080
CMD ["python", "-m", "app.main"]
