# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.148.1/containers/python-3/.devcontainer/base.Dockerfile

# [Choice] Python version: 3, 3.9, 3.8, 3.7, 3.6
ARG VARIANT="3"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT} AS venv-image

RUN echo "hi6"

# [Option] Install Node.js
ARG INSTALL_NODE="true"
ARG NODE_VERSION="lts/*"
RUN if [ "${INSTALL_NODE}" = "true" ]; then su vscode -c "source /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi
RUN python -m venv /ledfx/venv
ENV PATH="/ledfx/venv/bin:$PATH"

# Install dependencies and ledfx, remove unneeded packages
COPY .devcontainer/dev-apt-install.sh .
RUN chmod +x dev-apt-install.sh && ./dev-apt-install.sh \
    && rm -rf dev-apt-install.sh


### Create docker image from venv-image to install pip dependencies
#
FROM venv-image AS build-image
COPY --from=venv-image /ledfx/venv /ledfx/venv
ENV PATH="/ledfx/venv/bin:$PATH"

RUN python -m pip install -U pip setuptools wheel \
    && git clone --depth 1 https://github.com/LedFx/LedFx -b dev /ledfx-git
    # && cd /ledfx-git/frontend \
    # && npm install -g yarn
# WORKDIR /ledfx-git
# RUN python -m pip install -r requirements.txt \
#        -r requirements-dev.txt \
#        -r docs/requirements-docs.txt \
#     && python setup.py develop

EXPOSE 8888/tcp
EXPOSE 5353/udp
ENTRYPOINT [ "ledfx"]

# RUN frontend/npm install && npm start

# [Optional] If your pip requirements rarely change, uncomment this section to add them to the image.
# COPY requirements.txt /tmp/pip-tmp/
# RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
#    && rm -rf /tmp/pip-tmp