FROM python:3.12
COPY requirements.txt .
RUN pip3 install -r requirements.txt
RUN rm requirements.txt
WORKDIR /app
COPY . .
EXPOSE 8000
CMD [ "python3", "main.py" ]
