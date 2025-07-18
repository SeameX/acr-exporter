FROM mcr.microsoft.com/azure-cli:2.61.0

RUN adduser -D -g '' appuser

WORKDIR /app
RUN chown appuser:appuser /app

COPY --chown=appuser:appuser acr_exporter.py .

USER appuser

CMD ["python3", "-u", "acr_exporter.py"]
