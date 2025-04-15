# Running the Project with Docker

This section provides instructions to set up and run the project using Docker.

## Requirements

- Docker version 20.10 or higher
- Docker Compose version 1.29 or higher

## Environment Variables

The following environment variables are required:

- `APP_ENV`: Set to `production` for production environment.
- `MYSQL_ROOT_PASSWORD`: Password for the MySQL root user.
- `MYSQL_DATABASE`: Name of the MySQL database.

## Build and Run Instructions

1. Clone the repository and navigate to the project directory.
2. Build and start the services using Docker Compose:

   ```bash
   docker-compose up --build
   ```

3. Access the application at `http://localhost:8001`.

## Configuration

- The application uses a MySQL database. Ensure the `MYSQL_ROOT_PASSWORD` and `MYSQL_DATABASE` variables are set correctly in the `docker-compose.yml` file.
- Application data is stored in the `app_data` volume, and database data is stored in the `db_data` volume.

## Exposed Ports

- Application: `8001` (mapped to host `8001`)
- Database: Not exposed to the host system

For further details, refer to the `Dockerfile` and `docker-compose.yml` files included in the project.