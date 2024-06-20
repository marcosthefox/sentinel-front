evalscript_true_color = """
        //VERSION=3

        function setup() {
            return {
                input: [{
                    bands: ["B02", "B03", "B04"]
                }],
                output: {
                    bands: 3
                }
            };
        }

        function evaluatePixel(sample) {
            return [sample.B04, sample.B03, sample.B02];
        }
        """

# evalscript para obtener las bandas B02, B03, B04 y B08 
evalscript_ir = """
        //VERSION=3

        function setup() {
            return {
                input: [{
                    bands: ["B02", "B03", "B04", "B08"]
                }],
                output: {
                    bands: 4
                }
            };
        }

        function evaluatePixel(sample) {
            return [sample.B02, sample.B03, sample.B04, sample.B08];
        }
        """