import React from 'react';
import { useSelector } from 'react-redux';
import Button from '@material-ui/core/Button';
import TextField from '@material-ui/core/TextField';
import IconButton from '@material-ui/core/IconButton';
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import BugReportIcon from '@material-ui/icons/BugReport';

export default function FormDialog() {
    const WEBHOOK_URL =
        'https://discord.com/api/webhooks/801611956452720660/lcCg8hzCRZcxnA-99JVtqX_GYLfgUsr0AjDH4seDNQNEC8XSKkHModopgjTAuFodhNwI';
    const [open, setOpen] = React.useState(false);
    const [name, setName] = React.useState('');
    const [description, setDescription] = React.useState('');
    const settings = useSelector(state => state.settings);
    const infos = {
        userAgent: navigator.userAgent,
        language: navigator.language,
        platform: navigator.platform,
    };
    const handleClickOpen = () => {
        setOpen(true);
    };
    const handleClose = () => {
        setOpen(false);

        sendMessage({ text: JSON.stringify(infos) });
    };
    const sendMessage = async ({ avatar = '' }) => {
        const request = new XMLHttpRequest();
        request.open('POST', WEBHOOK_URL);

        request.setRequestHeader('Content-type', 'application/json');

        const params = {
            username: name,
            avatar_url: avatar,
            content: `

Description:
\`\`\`json
${JSON.stringify(description)}
\`\`\`
Infos:
\`\`\`json
${JSON.stringify(infos)}
\`\`\`
Settings:\`\`\`json
${JSON.stringify(settings)}
\`\`\`Logs-URL:
\`\`\`https://logsurl-are-incoming.com\`\`\`
`,
        };
        request.send(JSON.stringify(params));
    };
    return (
        <div style={{ display: 'inline-block' }}>
            <IconButton onClick={handleClickOpen}>
                <BugReportIcon aria-label="BugTracker" color="inherit" title="BugTracker" />
            </IconButton>
            <Dialog open={open} onClose={handleClose} aria-labelledby="form-dialog-title">
                <DialogTitle id="form-dialog-title">LedFx BugTracker</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Attention, if you abuse this service, Blade will hack you... No, serious!!
                        We need to pay 3,30€ per request
                    </DialogContentText>
                    <TextField
                        autoFocus
                        margin="dense"
                        value={name}
                        onChange={e => setName(e.target.value)}
                        id="name"
                        label="Name"
                        type="text"
                        fullWidth
                    />
                    <TextField
                        autoFocus
                        margin="dense"
                        value={description}
                        onChange={e => setDescription(e.target.value)}
                        id="description"
                        label="Description"
                        type="text"
                        fullWidth
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleClose} color="primary">
                        Cancel
                    </Button>
                    <Button onClick={handleClose} color="primary">
                        Subscribe
                    </Button>
                </DialogActions>
            </Dialog>
        </div>
    );
}
