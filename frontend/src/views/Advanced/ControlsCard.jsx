import React from 'react';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import Button from '@material-ui/core/Button';

import CloudUploadIcon from '@material-ui/icons/CloudUpload';
import CloudDownloadIcon from '@material-ui/icons/CloudDownload';
import PowerSettingsNewIcon from '@material-ui/icons/PowerSettingsNew';

const ControlsCard = () => {
    return (
        <Card>
            <CardHeader title="Controls" subheader="for development" />
            <CardContent>
                <Button
                    size="small"
                    startIcon={<CloudUploadIcon />}
                    variant="contained"
                    style={{ marginRight: '10px' }}
                >
                    Export Configuration
                </Button>
                <Button
                    size="small"
                    startIcon={<CloudDownloadIcon />}
                    variant="contained"
                    style={{ marginRight: '10px' }}
                >
                    Import Configuration
                </Button>
                <Button size="small" startIcon={<PowerSettingsNewIcon />} variant="contained">
                    Shutdown
                </Button>
            </CardContent>
        </Card>
    );
};

export default ControlsCard;
