FROM pycbc/pycbc-base-el7:v2.0-89a30fc

ENTRYPOINT ["/bin/bash", "-vc", "source /opt/pycbc/pycbc-software/bin/activate; exec $0 $@"]

USER pycbc
WORKDIR /opt/pycbc
