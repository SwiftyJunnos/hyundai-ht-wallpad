ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir "paho-mqtt>=2.1.0"

WORKDIR /app
COPY wallpad_protocol.py wallpad_command.py wallpad_monitor.py /app/

CMD ["python", "-u", "wallpad_monitor.py"]
