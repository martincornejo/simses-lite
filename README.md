# simses-lite

An experimental project that explores a simpler [simses](https://gitlab.lrz.de/open-ees-ses/simses) implementation. 
The goal is to design a new structure, and reduce the size of the project to its minimum,
so that it is easier for anyone to understand the code, use it and contribute.

For now simses-lite will only support the most basic features, if successful we will create a roadmap to convert it into simses v2.0 

## Principles:
1. **Aim for Modularity**: Design components to be modular with well-defined interfaces, facilitating easier maintenance and collaboration.
2. **Favor Composability**: To promote flexibility and reduce complexity, steering clear of deeply nested subclasses.
3. **Write Idiomatic Python**: Emphasize clarity and conciseness in your code. Strive for brevity while avoiding unnecessary verbosity to enhance readability.
4. **Emphasize Explicitness**: Ensure that all behaviors and states are clear and explicit. Models should solely represent state transitions based on inputs, with states being simple data objects that contain no methods.
5. **Prioritize Simplicity**: Strive for simplicity and ease of understanding over performance. However, performance remains important; regularly profile the code to identify and address bottlenecks.
6. **Avoid Premature Optimization**: Focus on the current requirements and avoid over-engineering by anticipating features that may not be needed in the future.
