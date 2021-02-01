import React from 'react';
import { useDispatch } from 'react-redux';
import { makeStyles } from '@material-ui/core/styles';
import Button from '@material-ui/core/Button';
import Dialog from '@material-ui/core/Dialog';
import AppBar from '@material-ui/core/AppBar';
import Toolbar from '@material-ui/core/Toolbar';
import Typography from '@material-ui/core/Typography';
import Slide from '@material-ui/core/Slide';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import SaveIcon from '@material-ui/icons/Save';
import AddSegmentDialog from './AddSegmentDialog';
import Segment from './Segment';
import { updateDisplayConfig } from 'modules/displays';
import { showdynSnackbar } from 'modules/ui';
import NavigateBeforeIcon from '@material-ui/icons/NavigateBefore';

const useStyles = makeStyles(theme => ({
    appBar: {
        position: 'relative',
        marginBottom: '1rem',
        background: theme.palette.background.default,
        color: theme.palette.text.primary,
    },
    title: {
        marginLeft: theme.spacing(2),
        flex: 1,
    },
    dialog: {
        background: theme.palette.background.default,
    },
}));

const Transition = React.forwardRef(function Transition(props, ref) {
    return <Slide direction="up" ref={ref} {...props} />;
});

export default function FullScreenDialog({ display, icon, className }) {
    const dispatch = useDispatch();
    const classes = useStyles();
    const [open, setOpen] = React.useState(false);
    const handleClickOpen = () => {
        setOpen(true);
    };

    const handleClose = () => {
        setOpen(false);
    };

    function getOverlapping(data) {
        const tmp = {};
        data.forEach(([name, start, end]) => {
            if (!tmp[name]) {
                tmp[name] = {};
                data.forEach(y => {
                    tmp[name].items = [];
                    tmp[name].overlap = false;
                    tmp[name].items.push([start, end]);
                });
            } else {
                tmp[name].items.push([start, end]);
            }
        });
        Object.keys(tmp).forEach(e =>
            tmp[e].items
                .sort(([startA], [startB]) => startA > startB)
                .forEach(([start, end], i) => {
                    if (tmp[e].items[i + 1]) {
                        const [startNew, endNew] = tmp[e].items[i + 1];
                        if (startNew <= end && endNew >= start) {
                            tmp[e].overlap = true;
                        }
                    }
                })
        );
        return tmp;
    }

    const handleSave = () => {
        const output = getOverlapping(display.segments);
        const overlap = Object.keys(output).find(k => output[k].overlap);
        if (overlap) {
            dispatch(
                showdynSnackbar({
                    message: `Overlapping in ${overlap} detected! Please Check your config`,
                })
            );
        } else {
            dispatch(updateDisplayConfig({ id: display.id, data: display.segments }));
            // setOpen(false);
        }
    };

    return (
        <>
            <Button
                variant="contained"
                color={'default'}
                onClick={handleClickOpen}
                size="small"
                className={className}
            >
                {icon || <AddCircleIcon />}
            </Button>
            <Dialog fullScreen open={open} onClose={handleClose} TransitionComponent={Transition}>
                <AppBar className={classes.appBar}>
                    <Toolbar>
                        <Button
                            autoFocus
                            color="primary"
                            variant="contained"
                            startIcon={<NavigateBeforeIcon />}
                            onClick={handleClose}
                            style={{ marginRight: '1rem' }}
                        >
                            back
                        </Button>
                        <Typography variant="h6" className={classes.title}>
                            {display.config.name}{' '}
                        </Typography>
                        <div>
                            <Button
                                autoFocus
                                color="primary"
                                variant="contained"
                                endIcon={<SaveIcon />}
                                onClick={handleSave}
                            >
                                save
                            </Button>
                        </div>
                    </Toolbar>
                </AppBar>

                <div
                    style={{
                        display: 'flex',
                        borderBottom: '1px dashed #aaa',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        margin: '0 1rem',
                    }}
                >
                    <Typography variant="caption">Segments-Settings</Typography>
                </div>
                {display.segments.length > 0 &&
                    display.segments.map((s, i) => (
                        <Segment s={s} i={i} key={i} display={display} />
                    ))}
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        margin: '0 1rem',
                    }}
                >
                    <AddSegmentDialog display={display} />
                </div>
            </Dialog>
        </>
    );
}
