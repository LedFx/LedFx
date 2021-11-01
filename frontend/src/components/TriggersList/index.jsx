import React from 'react';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import {
    Card,
    CardContent,
    Divider,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Typography,
} from '@material-ui/core';
import DeleteForeverIcon from '@material-ui/icons/DeleteForever';
import { getScenes } from 'modules/scenes';

import { useEffect } from 'react';

const styles = theme => ({});

const triggersNew = [];

class TriggerList extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            triggers: triggersNew,
        };
    }

    deleteTest = event => {
        console.log(event.target);
    };

    componentDidMount() {
        console.log(this.props.spotify);
        this.props.spotify.map(scene => {
            let sceneName = scene.name;
            let sceneId = scene.id;
            Object.keys(scene).map(function (key, index) {
                if (scene[key].constructor === Array) {
                    // console.log(scene[key]);
                    triggersNew.push({
                        songId: scene[key][0],
                        songName: scene[key][1],
                        position: scene[key][2],
                        sceneId: sceneId,
                        sceneName: sceneName,
                    });
                }
            });
            this.setState({ triggers: triggersNew });
        });
        // console.log(triggers);
    }

    componentDidUpdate(prevProps, prevState) {
        if (this.props.integrations !== prevProps.integrations) {
            triggersNew.length = 0;
            let temp = this.props.integrations.data;
            Object.keys(temp).map(function (key, index) {
                let temp1 = temp[key];
                let sceneName = temp1.name;
                let sceneId = temp1.name;
                Object.keys(temp1).map(function (key, index) {
                    console.log(temp1[key]);
                    if (temp1[key].constructor === Array) {
                        // console.log(scene[key]);
                        triggersNew.push({
                            songId: temp1[key][0],
                            songName: temp1[key][1],
                            position: temp1[key][2],
                            sceneId: sceneId,
                            sceneName: sceneName,
                        });
                    }
                });
            });
            this.setState({ triggers: triggersNew });
        }
    }

    render() {
        const {} = this.props;
        return (
            <Card>
                <CardContent>
                    {this.state.triggers.length > 0 ? (
                        <List>
                            <ListItem>
                                <ListItemText primary="Song" secondary="Position" />
                                <ListItemText primary="Scene Name" />
                            </ListItem>
                            {this.state.triggers.map((trigger, i) => (
                                <div key={i}>
                                    <ListItem>
                                        <ListItemText
                                            primary={trigger.songName}
                                            secondary={trigger.position}
                                        />
                                        <ListItemText primary={trigger.sceneName} />
                                        <ListItemIcon>
                                            <DeleteForeverIcon
                                                color="error"
                                                onClick={this.deleteTest}
                                                style={{ cursor: 'pointer' }}
                                            />
                                        </ListItemIcon>
                                    </ListItem>
                                    <Divider />
                                </div>
                            ))}
                        </List>
                    ) : (
                        <Typography>Add Some Triggers To View Them Here</Typography>
                    )}
                </CardContent>
            </Card>
        );
    }
}

export default connect(
    state => ({
        spotify: state.scenes.list,
        integrations: state.integrations.list.spotify,
    }),
    {}
)(withStyles(styles)(TriggerList));
