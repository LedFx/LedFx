import React from 'react';
import AceEditor from 'react-ace';

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import 'ace-builds/src-noconflict/mode-yaml';
import 'ace-builds/src-noconflict/theme-twilight';
import 'ace-builds/src-noconflict/theme-github';
import { Button } from '@material-ui/core';
import { FolderOpen, Save } from '@material-ui/icons';
import * as settingProxies from 'proxies/settings';

// const yaml = require('./ledfx-config.yml');
const yaml2 = `
crossfade: 1.0
custom_presets: {}
dev_mode: false
devices: []
fade: 1.0
host: 0.0.0.0
integrations: []
port: 8888
scenes: {}
virtuals: []

`;
function onChange(newValue) {
    // console.log('change', newValue);
}

const ConfigEditor = ({ raw = false }) => {
    const [yaml, setYaml] = React.useState(`
    crossfade: 1.0
    custom_presets: {}
    dev_mode: false
    devices: []
    fade: 1.0
    host: 0.0.0.0
    integrations: []
    port: 8888
    scenes: {}
    virtuals: []
    
    `)
    const load = async () => {
        const response = await settingProxies.getSystemConfig();
        if (response.statusText === 'OK') {
            setYaml(JSON.stringify({ ...response.data.config, ...{ ledfx_presets: undefined } }, null, 4))
        }
    }
    const save = async () => {
        console.log(yaml)
        const response = await settingProxies.importSystemConfig(JSON.parse(yaml));
        if (response.statusText !== 'OK') {
            console.log(response)
        }
    }
    return raw ? (
        <div style={{ flex: 1 }} >
            <Button variant="outlined" size="small" startIcon={<FolderOpen />} onClick={load}>Load current config</Button>
            <Button variant="outlined" size="small" startIcon={<Save />} onClick={save}>Save</Button>
            <AceEditor
                mode="yaml"
                theme={window.localStorage.getItem('blade') === '3' ? 'twilight' : 'github'}
                onChange={setYaml}
                value={yaml}
                name="UNIQUE_ID_OF_DIV"
                editorProps={{ $blockScrolling: true }}
                placeholder={'AWESOME SHIT INCOMING.... - hacked by Blade'}
                style={{ width: '100%' }}
            />
        </div>
    ) : (
        <Card>
            <CardHeader title="Config Editor" subheader="for development" />
            <CardContent>
                <AceEditor
                    mode="yaml"
                    theme={window.localStorage.getItem('blade') === '3' ? 'twilight' : 'github'}
                    onChange={onChange}
                    value={yaml2}
                    name="UNIQUE_ID_OF_DIV"
                    editorProps={{ $blockScrolling: true }}
                    placeholder={'AWESOME SHIT INCOMING.... - hacked by Blade'}
                    style={{ width: '100%' }}
                />
            </CardContent>
        </Card>
    );
}

export default ConfigEditor;
