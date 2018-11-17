FROM my_python:latest
COPY ./coap_server.py /code/
WORKDIR /code
CMD ["python", "coap_server.py"]
