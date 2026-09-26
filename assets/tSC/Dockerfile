FROM python:2

WORKDIR /vitors_directory

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./test-script.py" ]
