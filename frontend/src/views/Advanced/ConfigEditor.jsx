import React from 'react';
import AceEditor from 'react-ace';

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import 'ace-builds/src-noconflict/mode-yaml';
import 'ace-builds/src-noconflict/theme-twilight';
import 'ace-builds/src-noconflict/theme-github';

// const yaml = require('./ledfx-config.yml');
const yaml2 = `
crossfade: 1.0
custom_presets: {}
dev_mode: false
devices: []
fade: 1.0
host: 0.0.0.0
integrations: []
max_workers: 10
port: 8888
scenes: {}
virtuals: []

`;
function onChange(newValue) {
    // console.log('change', newValue);
}

const ConfigEditor = () => {
    return (
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
};

export default ConfigEditor;
