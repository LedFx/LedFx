class DeviceWebsocketConnection {
    constructor(deviceId) {
        this.deviceId = deviceId

        this.onConnected = function(){};
        this.onDisconnected = function(){};
        this.onPixelUpdate = function(){};
        this.pixelRefreshRate = 30;
    }

    connect() {
        this.disconnect();

        var self = this;
        var wsUri = (window.location.protocol=='https:'&&'wss://'||'ws://')+
            window.location.host+'/device/'+this.deviceId+'/ws';
        this.conn = new WebSocket(wsUri);

        this.conn.onopen = function() {
            self.onConnected()
            self.getPixelData()
        };

        this.conn.onmessage = function(e) {
            var data = JSON.parse(e.data);
            switch (data.action) {
                case 'update_pixels':
                    self.onPixelUpdate(data)
                    break;
            }
        };

        this.conn.onclose = function() {
            self.conn = null;
            self.onDisconnected()
        };
    }

    disconnect() {
        if (this.conn != null) {
            this.conn.close();
            this.conn = null;
        }
    }

    toggleConnection() {
        if (this.isConnected()) {
            this.disconnect();
        } else {
            this.connect();
        }
    }
    
    isConnected() {
        return this.conn != null;
    }

    getPixelData() {
        if (this.conn != null) {
            this.conn.send('get_pixels');

            var self = this;
            setTimeout(function() {
                self.getPixelData();
            }, 1000 / self.pixelRefreshRate);
        }
    }
}