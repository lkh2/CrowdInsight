import streamlit.components.v1 as components
import tempfile
import os

# --- Component Generation Function ---
def generate_component(name, template="", script=""):
    """Generates a Streamlit component from HTML/CSS/JS strings."""
    dir = f"{tempfile.gettempdir()}/{name}"
    if not os.path.isdir(dir): os.mkdir(dir)
    fname = f'{dir}/index.html'
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <link href='https://fonts.googleapis.com/css?family=Poppins' rel='stylesheet'>
                <link href='https://fonts.googleapis.com/css?family=Playfair Display' rel='stylesheet'>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{name}</title>
                <script>
                    // --- Streamlit Communication Boilerplate ---
                    function sendMessageToStreamlitClient(type, data) {{
                        const outData = Object.assign({{
                            isStreamlitMessage: true,
                            type: type,
                        }}, data);
                        window.parent.postMessage(outData, "*");
                    }}

                    const Streamlit = {{
                        setComponentReady: function() {{
                            sendMessageToStreamlitClient("streamlit:componentReady", {{apiVersion: 1}});
                        }},
                        setFrameHeight: function(height) {{
                            sendMessageToStreamlitClient("streamlit:setFrameHeight", {{height: height}});
                        }},
                        setComponentValue: function(value) {{
                            sendMessageToStreamlitClient("streamlit:setComponentValue", {{value: value}});
                        }},
                        RENDER_EVENT: "streamlit:render",
                        events: {{
                            addEventListener: function(type, callback) {{
                                window.addEventListener("message", function(event) {{
                                    if (event.data.type === type) {{
                                        event.detail = event.data
                                        callback(event);
                                    }}
                                }});
                            }}
                        }}
                    }}
                    // --- End Streamlit Boilerplate ---
                </script>
                {template}
            </head>
            <body>
                <div id="component-root"></div>
            </body>
            <script>
                {script}
            </script>
            </html>
        """)

    # Declare the component using the path to the generated index.html
    _component_func = components.declare_component(name, path=str(dir))

    # Return a wrapper function that takes component_data and other Streamlit args
    def component_wrapper(component_data, key=None, default=None):
        component_value = _component_func(component_data=component_data, key=key, default=default)
        return component_value
    return component_wrapper 