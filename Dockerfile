FROM apify/actor-python:3.11

COPY requirements.txt ./
RUN echo "Python version:" && python --version \
 && echo "Installing dependencies:" && pip install -r requirements.txt \
 && echo "All installed Python packages:" && pip freeze

COPY . ./

# `-m src` runs src/__main__.py, which awaits main(). `-m src.main` would
# import the module and exit without ever running the Actor.
CMD ["python3", "-m", "src"]
