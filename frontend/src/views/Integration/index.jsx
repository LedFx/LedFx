import React from 'react';

const IntegrationView = props => {
    console.log(props);
    const { integrationId } = props.match.params;
    console.log(integrationId);
    return <div>BOOOM</div>;
};

export default IntegrationView;
