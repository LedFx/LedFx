# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.148.1/containers/python-3/.devcontainer/base.Dockerfile

# [Choice] Python version: 3, 3.9, 3.8, 3.7, 3.6
ARG VARIANT="3"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

# [Option] Install Node.js
ARG INSTALL_NODE="true"
ARG NODE_VERSION="lts/*"
RUN if [ "${INSTALL_NODE}" = "true" ]; then su vscode -c "source /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi




RUN python -m venv /ledfx/venv
ENV PATH="/ledfx/venv/bin:$PATH"

# Install dependencies and ledfx, remove uneeded packages
#
# TRY WITH build-essential and portaudio19-dev ONLY
# 
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libc-dev \
    && apt-get install -y \
        alsa-utils \
        libasound2 \
        libasound2-plugins \
        portaudio19-dev \
        pulseaudio \
    && pip install ledfx-dev \
    && apt-get purge -y gcc libc-dev \
    && apt-get clean -y \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Add user `ledfx` and create home folder
RUN useradd --create-home ledfx
# Set the working directory in the container
WORKDIR /home/ledfx
USER ledfx

# Expose port 8888 for web server and 5353 for mDNS discovery
EXPOSE 8888/tcp
EXPOSE 5353/udp
ENTRYPOINT [ "ledfx"]
CMD ["--host 0.0.0.0","--port 8888"]

# RUN frontend/npm install && npm start


# [Optional] If your pip requirements rarely change, uncomment this section to add them to the image.
# COPY requirements.txt /tmp/pip-tmp/
# RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
#    && rm -rf /tmp/pip-tmp

# [Optional] Uncomment this section to install additional OS packages.
# RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#     && apt-get -y install --no-install-recommends <your-package-list-here>

# [Optional] Uncomment this line to install global node packages.
# RUN su vscode -c "source /usr/local/share/nvm/nvm.sh && npm install -g <your-package-here>" 2>&1
# RUN su vscode -c "source /usr/local/share/nvm/nvm.sh && frontend/npm install" 2>&1