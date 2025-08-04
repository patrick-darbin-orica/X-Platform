import asyncio
import numpy as np
from flask import Flask, Response, stream_with_context

app = Flask(__name__)

# HTML template to display arrays
html_template = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Random Numpy Arrays</title>
  </head>
  <body>
    <h1>Random Numpy Arrays</h1>
    {% for array in arrays %}
      <pre>{{ array }}</pre>
    {% endfor %}
  </body>
</html>
"""

async def generate_random_arrays():
    """Asynchronously generate random numpy arrays."""
    while True:
        random_array = np.random.rand(10, 10)  # Generate a 10x10 random array
        await asyncio.sleep(1)  # Simulate some delay
        yield random_array

async def get_random_arrays():
    async for array in generate_random_arrays():
        yield array

@app.route('/random_arrays')
async def random_arrays():
    async def generate():
        async for array in get_random_arrays():
            array_str = np.array2string(array, separator=', ')
            yield f"<pre>{array_str}</pre><br>"

    return Response(stream_with_context(generate()), mimetype='text/html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
