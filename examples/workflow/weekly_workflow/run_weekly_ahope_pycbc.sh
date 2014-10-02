GPS_START_TIME=967593543
GPS_END_TIME=967679943
export LOGPATH=/usr1/${USER}/log
export PIPEDOWNLOG=/usr1/${USER}
export HTMLDIR=/home/${USER}/public_html/workflow/development/weekly_ahope/test
mkdir -p $LOGPATH

# Generate the workflow
python weekly_ahope.py --config-files weekly_ahope_pycbc.ini pipedown.ini inj.ini \
--config-overrides workflow:start-time:${GPS_START_TIME} \
workflow:end-time:${GPS_END_TIME} \
workflow:workflow-html-basedir:${HTMLDIR} \
workflow:pipedown-tmp-space:${PIPEDOWNLOG} \
workflow:pipedown-log-path:${LOGPATH}

# Move some files needed to do pegasus planning to the workspace folder
cp plan.sh ${GPS_START_TIME}-${GPS_END_TIME}/
cp pegasus.conf ${GPS_START_TIME}-${GPS_END_TIME}/

echo 'cat <<END_OF_TEXT' >  temp.sh
cat "site-local.xml"                 >> temp.sh
echo 'END_OF_TEXT'       >> temp.sh
bash temp.sh > "${GPS_START_TIME}-${GPS_END_TIME}/site-local.xml"

# Plan the workflow
cd ${GPS_START_TIME}-${GPS_END_TIME}/
sh plan.sh weekly_ahope.dax ${LOGPATH}
